from bs4 import BeautifulSoup
import configparser
import logging
from tqdm import tqdm
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger()

# Function to load the details from the configuration file
def load_details(config_path='config.ini'):
    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        logger.error(f"Configuration file {config_path} not found.")
        return None
    config.read(config_path)
    try:
        html_file_path = config.get('Anghami', 'html_file_path')
        client_id = config.get('Spotify', 'client_id')
        client_secret = config.get('Spotify', 'client_secret')
        redirect_url = config.get('Spotify', 'redirect_url')
        username = config.get('Spotify', 'username')
        spotify_playlist_name = config.get('Spotify', 'playlist_name')
        save_to_text = config.getboolean('General', 'save_to_text')
        txt_save_path = config.get('General', 'txt_save_path')
        txt_song_artist_separator = config.get('General', 'txt_song_artist_separator')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.error(f"Error reading configuration: {e}")
        return None
    return html_file_path, client_id, client_secret, redirect_url, username, spotify_playlist_name, save_to_text, txt_save_path, txt_song_artist_separator

def read_html_file(html_file_path):
    try:
        with open(html_file_path, encoding="utf8") as f:
            content = f.read()
        return content
    except FileNotFoundError:
        logger.error(f"HTML file {html_file_path} not found.")
        return None

def extract_songs_and_artists(content):
    soup = BeautifulSoup(content, 'html.parser')
    class_lst = ["cell cell-title", "cell cell-title marquee"]
    song_divs = soup.find_all("div", class_=class_lst)
    artist_divs = soup.find_all("div", {"class": "cell cell-artist"})
    
    songs = [div.find("span").text if div.find("span") else "" for div in song_divs]
    artists = [div.text if div else "" for div in artist_divs]
    
    return songs, artists

def save_playlist_to_text(songs, artists, txt_save_path, txt_song_artist_separator):
    with open(txt_save_path, 'w', encoding="utf8") as fp:
        for song, artist in zip(songs, artists):
            fp.write(f"{song}{txt_song_artist_separator}{artist}\n")

def authenticate_spotify(client_id, client_secret, redirect_url, username):
    scope = 'playlist-modify-public'
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                                       client_secret=client_secret,
                                                       redirect_uri=redirect_url,
                                                       scope=scope,
                                                       username=username))
        return sp
    except spotipy.SpotifyException as e:
        logger.error(f"Spotify authentication failed: {e}")
        return None

def create_spotify_playlist(sp, username, spotify_playlist_name):
    try:
        playlist = sp.user_playlist_create(user=username, name=spotify_playlist_name, public=True,
                                           description="Imported from Anghami")
        return playlist['id']
    except spotipy.SpotifyException as e:
        logger.error(f"Failed to create Spotify playlist: {e}")
        return None

def search_and_add_tracks(sp, playlist_id, songs, artists, username):
    not_found = []
    for song, artist in tqdm(zip(songs, artists), total=len(songs), bar_format="{l_bar}{bar}{r_bar}", colour='green'):
        try:
            res = sp.search(q=f"{song} {artist}", type='track', limit=1)
            if len(res['tracks']['items']) > 0:
                uri = res['tracks']['items'][0]['uri']
                sp.user_playlist_add_tracks(user=username, playlist_id=playlist_id, tracks=[uri])
            else:
                not_found.append(f"{song} {artist}")
        except spotipy.SpotifyException as e:
            logger.error(f"Spotify Error: {str(e)}")
            not_found.append(f"{song} {artist}")

    return not_found

def main():
    # Load details from configuration file
    config_details = load_details()
    if not config_details:
        return
    
    html_file_path, client_id, client_secret, redirect_url, username, spotify_playlist_name, save_to_text, txt_save_path, txt_song_artist_separator = config_details

    # Read the HTML file
    content = read_html_file(html_file_path)
    if not content:
        return

    # Extract songs and artists from the HTML
    songs, artists = extract_songs_and_artists(content)
    
    # Check if the number of songs matches the number of artists
    if len(songs) != len(artists):
        logger.error(f"Error: Number of songs ({len(songs)}) and artists ({len(artists)}) do not match.")
        return

    # Print the playlist details
    logger.info("\nPlaylist Details:")
    for song, artist in zip(songs, artists):
        logger.info(f"{song} {txt_song_artist_separator} {artist}")

    # Save the playlist to a text file
    if save_to_text:
        save_playlist_to_text(songs, artists, txt_save_path, txt_song_artist_separator)
        logger.info("Playlist saved to text file.")

    # Authenticate and create a new playlist on Spotify
    sp = authenticate_spotify(client_id, client_secret, redirect_url, username)
    if not sp:
        return

    playlist_id = create_spotify_playlist(sp, username, spotify_playlist_name)
    if not playlist_id:
        return

    # Search and add tracks to the Spotify playlist
    logger.info("Importing playlist to Spotify...")
    not_found = search_and_add_tracks(sp, playlist_id, songs, artists, username)

    logger.info("Playlist import completed.")

    # Print the not found songs
    if len(not_found) > 0:
        logger.info("\nThe following songs could not be found on Spotify:")
        for song in not_found:
            logger.info(song)

if __name__ == '__main__':
    main()

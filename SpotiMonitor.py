import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred
import os
import subprocess
import concurrent.futures
import threading
import argparse
import time

thread_local = threading.local()

def get_user_id(spotify_connection):
    return spotify_connection.current_user()["id"]

def get_playlists(spotify_connection):
    return [playlist["name"] for playlist in spotify_connection.current_user_playlists()["items"]]

def get_playlist_id(spotify_connection, playlist_name):
    playlists = spotify_connection.current_user_playlists()

    for playlist in playlists["items"]:
        if playlist["name"] == playlist_name:
            return playlist["id"]

def get_playlist_tracks(spotify_connection, playlist_name):
    user_id = get_user_id(spotify_connection)
    playlist_id = get_playlist_id(spotify_connection, playlist_name)

    response = spotify_connection.user_playlist_tracks(user_id, playlist_id, limit=100)
    results = response["items"]

    while len(results) < response["total"]:
        response = spotify_connection.user_playlist_tracks(
            user_id, playlist_id, limit=100, offset=len(results)
        )
        results.extend(response["items"])

    track_list = [result["track"] for result in results]

    track_information = []
    for track in track_list:
        track_id = track["id"]
        track_link = track["external_urls"]["spotify"]
        track_name = track["name"]

        artists = [artist["name"] for artist in track["artists"]]
        track_artists = ""
        for artist in artists:
            track_artists += artist

            if not artist == artists[-1]:
                track_artists += " & "

        track_information.append({"id": track_id, "link": track_link, "artists": track_artists, "name": track_name})
    
    return track_information

def download_track(track_name, track_link, destination_folder, verbosity=False):
    if verbosity:
        print(f"\tDownloading track: {track_name}")
    
    if not os.path.exists(destination_folder):
        print("Destination folder does not exist!")
        exit(1)

    subprocess.run(["spotdl", "-o", destination_folder, "--use-youtube", track_link], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["spotdl", "-o", destination_folder, track_link], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def download_playlist(playlist_tracks, base_folder, playlist_name, threads=16, verbosity=False):
    if verbosity:
        print(f"\nDownloading playlist: {playlist_name}\n")
    
    playlist_folder = f"{base_folder}\\{playlist_name}"

    if not os.path.exists(playlist_folder):
        os.mkdir(playlist_folder)

    offline_tracks = [f for f in os.listdir(f"{base_folder}\\{playlist_name}") if ".mp3" in f]

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        for track in playlist_tracks:
            track_title = " - ".join([track["artists"], track["name"]]) + ".mp3"

            if track_title not in offline_tracks:
                executor.submit(download_track, track_title[:-4], track["link"], playlist_folder, verbosity)
    
    cleanup_playlist_files(playlist_tracks, base_folder, playlist_name, verbosity)

def cleanup_playlist_files(playlist_tracks, base_folder, playlist_name, verbosity=False):
    if verbosity:
        print("\n\tCleaning up leftover files...")
    offline_tracks = [f for f in os.listdir(f"{base_folder}\\{playlist_name}") if ".mp3" in f]
    
    for track in offline_tracks:
        artist = track.split("-")[0].strip()
        title = "-".join(track.split("-")[1:])[:-4].strip()

        if not any(playlist_track["artists"] == artist for playlist_track in playlist_tracks) and not any(playlist_track["name"] == title for playlist_track in playlist_tracks):
            os.remove(f"{base_folder}\\{playlist_name}\\{track}")

    tracking_files = [f for f in os.listdir(f"{base_folder}\\{playlist_name}") if ".spotdlTrackingFile" in f]
    for f in tracking_files:
        os.remove(f"{base_folder}\\{playlist_name}\\{f}")
            
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", dest="playlist", type=str, help="The target playlist.")
    parser.add_argument("-o", dest="output_folder", metavar="FOLDER", type=str, required=True, help="The path of the output folder.")
    parser.add_argument("-t", dest="threads", metavar="THREADS", type=int, default=8, help="The number of threads to use while downloading new tracks.")
    parser.add_argument("--monitor", dest="monitor", action="store_true", help="Monitor playlist(s) for any changes.")
    parser.add_argument("--all", dest="all", action="store_true", help="Download all playlists.")
    parser.add_argument("-v", dest="verbosity", action="store_true", help="Show progress.")

    args = parser.parse_args()
    playlist_name = args.playlist
    output_folder = args.output_folder
    threads = args.threads
    monitor = args.monitor
    download_all = args.all
    verbosity = args.verbosity

    scope = "playlist-read-private"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_id, client_secret= cred.client_secret, redirect_uri=cred.redirect_url, scope=scope))

    if monitor:
        while True:
            if playlist_name:
                playlist_tracks = get_playlist_tracks(sp, playlist_name)
                download_playlist(playlist_tracks, output_folder, playlist_name, threads, verbosity)
            elif download_all:
                playlists = [playlist["name"] for playlist in sp.current_user_playlists()["items"]]            
                for playlist in playlists:
                    playlist_tracks = get_playlist_tracks(sp, playlist)
                    download_playlist(playlist_tracks, output_folder, playlist, threads, verbosity)
                      
            time.sleep(150)
    else:
        if playlist_name:
            playlist_tracks = get_playlist_tracks(sp, playlist_name)
            download_playlist(playlist_tracks, output_folder, playlist_name, threads, verbosity)
        elif download_all:
            playlists = [playlist["name"] for playlist in sp.current_user_playlists()["items"]]            
            for playlist in playlists:
                playlist_tracks = get_playlist_tracks(sp, playlist)
                download_playlist(playlist_tracks, output_folder, playlist, threads, verbosity)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        quit()

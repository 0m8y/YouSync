![YouSync Logo](YouSyncDev/gui/assets/images/YouSyncLogo.png)

\*\***NEW**\*\* *Official website*: https://yousync-app.github.io/

YouSync is an application that allows you to synchronize your playlists with your PC. By saving the desired playlist and assigning it to a folder on your computer, YouSync takes care of downloading all the songs in MP3 format and retrieving the associated metadata. Once the playlist is on your computer, you just need to press a button to synchronize it again.

## YouSync Features

- **Playlist Synchronization**: Sync your YouTube playlists on your PC with a single click.
- **Music Downloading and Metadata Retrieval**: Saves songs in MP3 format. Retrieves metadata for optimal organization.
- **Graphic Interface**: The graphical interface is now available!
- **Youtube Support**: Sync Youtube playlists.
- **Spotify Support**: Sync Spotify playlists.
- **Apple Music Support**: Sync Apple Music playlists.
- **Several playlists in the same folder**: Currently, it's possible to have several playlists in the same folder, but there's a thumbnail display bug.
- **Upgrade Playlists Folder Recover**: Instant recover.
- **Performance improvement**: Improved performance and application fluidity.
- **Platform thumbnail**: Add the logo of the playlist's platform to show where the playlist comes from
- **Platform filter**: To filter only the playlists of a platform. For example, display only youtube playlists.
- **2 new buttons on the playlist page**: One button redirects to the backup folder, another to the playlist link.

### Latests Features
- **Improve Installer**: No need to have python installed, installation is now just a click away!
- **Linux & macOS**: Compatibility with macOS and linux is under development.
  
### Upcoming Features
- **SoundCloud Support**: Sync SoundCloud playlists.

## Compatibility

- **Windows**: YouSync has been tested and is confirmed to work on Windows.
- **Linux and macOS**: Testing on Linux and macOS has not been completed yet but will be done soon.

## Installation

To install YouSync, simply run `YouSyncInstaller.exe` and follow the installation wizard instructions.

## Usage

1. **Launch App**:
   Once the installation is complete, you can launch the YouSync application from the Start menu or by running `YouSync.exe` in the installation folder.

## Technical Details

- **Programming Language**: Python
- **Download Library**: `pytube` for audio retrieval.
- **Browser Automation**: `selenium` for retrieving metadata and playlist songs.
- **Data Storage**: Information is stored in the specified folder when adding the playlist, in a `.yousync` subfolder as JSON files.

## Contributing

Contributions are welcome! To submit changes, follow these steps:

1. Fork the repository
2. Create a branch for your feature (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push your branch (`git push origin my-new-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

> **Note**
> Users are responsible for their actions and any potential legal consequences. We do not support the unauthorized downloading of copyrighted material and assume no responsibility for users' actions.

---

Thank you for using YouSync! If you have any questions or suggestions, feel free to open an issue on GitHub.

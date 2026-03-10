# Installation

## Requirements

- Python 3.13+
- WeasyPrint system libraries (Linux/macOS only — see below)

## Install LeafPress

=== "uv"

    ```bash
    uv add leafpress
    ```

=== "pip"

    ```bash
    pip install leafpress
    ```

=== "pipx (global CLI)"

    ```bash
    pipx install leafpress
    ```

### With Desktop UI

The menu bar / system tray app requires PyQt6:

=== "uv"

    ```bash
    uv add 'leafpress[ui]'
    uv sync --extra ui
    ```

=== "pip"

    ```bash
    pip install 'leafpress[ui]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[ui]'
    ```

## WeasyPrint System Dependencies

LeafPress uses [WeasyPrint](https://doc.courtbouillon.org/weasyprint/) for PDF rendering. WeasyPrint requires Pango and related libraries.

### Ubuntu / Debian

```bash
sudo apt-get install -y \
  libpango-1.0-0 \
  libharfbuzz0b \
  libpangoft2-1.0-0 \
  libfontconfig1
```

### Fedora / RHEL

```bash
sudo dnf install pango harfbuzz fontconfig
```

### macOS

```bash
brew install pango
```

### Windows

On Windows, WeasyPrint can be installed via pip. GTK+ libraries may be needed — see the [WeasyPrint Windows installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).

## Verify Installation

```bash
leafpress --version
leafpress --help
```

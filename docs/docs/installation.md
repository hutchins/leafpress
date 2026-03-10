# Installation

## Requirements

- Python 3.13+
- WeasyPrint system libraries (only if you need PDF output — see below)

## Install LeafPress

The base install supports DOCX, HTML, ODT, EPUB output and DOCX import — no system dependencies required.

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

### With PDF Support

PDF output requires WeasyPrint and its system libraries (Pango, HarfBuzz — see below).

=== "uv"

    ```bash
    uv add 'leafpress[pdf]'
    ```

=== "pip"

    ```bash
    pip install 'leafpress[pdf]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[pdf]'
    ```

### With Desktop UI

The menu bar / system tray app requires PyQt6:

=== "uv"

    ```bash
    uv add 'leafpress[ui]'
    ```

=== "pip"

    ```bash
    pip install 'leafpress[ui]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[ui]'
    ```

### Everything

Install all optional features (PDF + UI):

=== "uv"

    ```bash
    uv add 'leafpress[all]'
    ```

=== "pip"

    ```bash
    pip install 'leafpress[all]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[all]'
    ```

## WeasyPrint System Dependencies

LeafPress uses [WeasyPrint](https://doc.courtbouillon.org/weasyprint/) for PDF rendering. WeasyPrint requires Pango and related libraries. These are **only needed if you install `leafpress[pdf]` or `leafpress[all]`**.

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

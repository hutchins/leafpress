# Installation

## Requirements

- Python 3.13+
- WeasyPrint system libraries (only if you need PDF output — see below)

## Install LeafPress

To use LeafPress as a **CLI tool or desktop UI**, install it globally with `uv tool` or `pipx`. To use it as a **Python library** in a project, use `uv add` or `pip install`.

### Base

DOCX, HTML, ODT, EPUB output and document import — no system dependencies required.

=== "uv tool"

    ```bash
    uv tool install leafpress
    ```

=== "pipx"

    ```bash
    pipx install leafpress
    ```

=== "uv"

    ```bash
    uv add leafpress
    ```

=== "pip"

    ```bash
    pip install leafpress
    ```

### With PDF Support

PDF output requires WeasyPrint and its system libraries (Pango, HarfBuzz — see below).

=== "uv tool"

    ```bash
    uv tool install 'leafpress[pdf]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[pdf]'
    ```

=== "uv"

    ```bash
    uv add 'leafpress[pdf]'
    ```

=== "pip"

    ```bash
    pip install 'leafpress[pdf]'
    ```

### With Desktop UI

The menu bar / system tray app requires PyQt6:

=== "uv tool"

    ```bash
    uv tool install 'leafpress[ui]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[ui]'
    ```

=== "uv"

    ```bash
    uv add 'leafpress[ui]'
    ```

=== "pip"

    ```bash
    pip install 'leafpress[ui]'
    ```

### Everything

All optional features (PDF + UI):

=== "uv tool"

    ```bash
    uv tool install 'leafpress[all]'
    ```

=== "pipx"

    ```bash
    pipx install 'leafpress[all]'
    ```

=== "uv"

    ```bash
    uv add 'leafpress[all]'
    ```

=== "pip"

    ```bash
    pip install 'leafpress[all]'
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

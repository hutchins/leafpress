# Docker

Run leafpress in a container — no system dependencies to install.

## Building the image

```bash
docker build -t leafpress .
```

## Usage

### Convert a local MkDocs project

Mount your project directory into the container:

```bash
docker run --rm -v $(pwd):/work leafpress convert /work
```

### Run as a non-root user (recommended)

The image runs as root by default so it can write to mounted directories owned by any user. Running as your own UID is safer, especially when converting repositories you don't control. It also means the generated files are owned by you rather than root:

```bash
docker run --rm --user "$(id -u):$(id -g)" -v $(pwd):/work leafpress convert /work
```

The image also includes an unprivileged `leafpress` user (`--user leafpress`) for cases where no host directory needs to be written. Git version info works with any UID: the image marks mounted repositories as a git `safe.directory`.

Base images are pinned by digest, so rebuilds start from the same Python and uv layers. System packages from `apt-get` aren't pinned, so two builds of the same commit can still differ slightly.

### Choose an output format

```bash
docker run --rm -v $(pwd):/work leafpress convert /work -f docx
docker run --rm -v $(pwd):/work leafpress convert /work -f all
```

### Custom output directory

```bash
docker run --rm \
  -v $(pwd):/work \
  -v $(pwd)/dist:/out \
  leafpress convert /work -o /out
```

### Branding via config file

```bash
docker run --rm \
  -v $(pwd):/work \
  leafpress convert /work -c /work/leafpress.yml
```

### Branding via environment variables

```bash
docker run --rm \
  -e LEAFPRESS_COMPANY_NAME="Acme Corp" \
  -e LEAFPRESS_PROJECT_NAME="Platform Docs" \
  -e LEAFPRESS_PRIMARY_COLOR="#1a73e8" \
  -v $(pwd):/work \
  leafpress convert /work
```

See [Configuration — Environment variables](configuration.md#environment-variables) for the full list.

## CI / CD

### GitHub Actions

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Build leafpress image
        run: docker build -t leafpress .

      # Pass values through env: rather than writing ${{ ... }} inside run:,
      # so they can't be interpreted as shell code.
      - name: Convert docs
        env:
          LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
          LEAFPRESS_PROJECT_NAME: ${{ github.event.repository.name }}
        run: |
          docker run --rm \
            --user "$(id -u):$(id -g)" \
            -e LEAFPRESS_COMPANY_NAME \
            -e LEAFPRESS_PROJECT_NAME \
            -v "$GITHUB_WORKSPACE:/work" \
            leafpress convert /work -f pdf -o /work/output

      - uses: actions/upload-artifact@v7
        with:
          name: docs-pdf
          path: output/
```

### GitLab CI

```yaml
build-docs:
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t leafpress .
    - docker run --rm
        -e LEAFPRESS_COMPANY_NAME="$COMPANY_NAME"
        -e LEAFPRESS_PROJECT_NAME="$CI_PROJECT_NAME"
        -v $CI_PROJECT_DIR:/work
        leafpress convert /work -f pdf -o /work/output
  artifacts:
    paths:
      - output/
```

## Remote sources

Convert directly from a git URL without cloning locally:

```bash
docker run --rm -v $(pwd)/output:/out \
  leafpress convert https://github.com/org/repo -o /out
```

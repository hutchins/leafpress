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
      - uses: actions/checkout@v4

      - name: Build leafpress image
        run: docker build -t leafpress .

      - name: Convert docs
        run: |
          docker run --rm \
            -e LEAFPRESS_COMPANY_NAME="${{ vars.COMPANY_NAME }}" \
            -e LEAFPRESS_PROJECT_NAME="${{ github.event.repository.name }}" \
            -v ${{ github.workspace }}:/work \
            leafpress convert /work -f pdf -o /work/output

      - uses: actions/upload-artifact@v4
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

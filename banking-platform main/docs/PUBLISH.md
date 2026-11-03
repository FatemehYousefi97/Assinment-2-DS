# GitHub / Docker Hub delivery procedure

No GitHub repository or Docker Hub image has been published by the project generation process. Publishing requires your account credentials and an actual Docker host.

## GitHub

```bash
git init
git add .
git commit -m "Implement Assignment 2 distributed banking platform"
# Create a repository in your own GitHub account, then:
git remote add origin https://github.com/YOUR_USER/distributed-banking.git
git branch -M main
git push -u origin main
```

`.env` is excluded by `.gitignore`; inspect `git status` to ensure no real secrets or generated runtime data are included. Add your university submission metadata and check repository visibility requirements.

## Docker Hub

```bash
docker login
bash scripts/publish_images.sh YOUR_DOCKERHUB_USER v1
```

The single application image serves Gateway, Coordinator and every shard replica by selecting a different Compose command. PostgreSQL uses the official `postgres:16-alpine` image; it is not falsely presented as custom-built. In university delivery, publish the app image and document the official DB image dependency.

To run the published application image, replace each `build: .` in the Compose anchors with `image: YOUR_DOCKERHUB_USER/distributed-banking:v1` and verify the exact final config with `docker compose config` before deployment.

Include GitHub URL, Docker Hub URL, the technical PDF, demo video URL, and the real experimental outputs in LMS. Do not fabricate published URLs; keep this file as instructions until upload is complete.


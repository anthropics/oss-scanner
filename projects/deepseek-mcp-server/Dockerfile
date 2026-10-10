FROM node:22-bookworm

# The scanner supplies a clean public checkout and removes its production
# .dockerignore when using this enrollment-local Dockerfile. Keep the tests
# and development dependencies available for the offline audit.
COPY . /src
WORKDIR /src
RUN npm ci --include=dev --no-audit --no-fund \
    && npm test

CMD ["bash"]

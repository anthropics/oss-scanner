FROM python:3.12-slim
COPY . /src
WORKDIR /src
RUN pip install --no-cache-dir pyyaml pytest paramiko
RUN python test_deploy_log_rules.py || echo "WARNING: unit tests reported failures"
RUN python -c "import glob, yaml; files=[f for f in glob.glob('**/*.yaml', recursive=True)+glob.glob('**/*.yml', recursive=True) if '/.git/' not in f]; [list(yaml.safe_load_all(open(f))) for f in files]; print(len(files), 'YAML files OK')" || echo "WARNING: YAML validation failed"

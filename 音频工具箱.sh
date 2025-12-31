cd "${0%/*}" || exit
[ ! -d ".venv" ] && python3 -m venv --clear --upgrade-deps --copies ".venv"
[ -d ".venv" ] && python3 -m venv --upgrade --upgrade-deps --copies ".venv"
source ".venv/bin/activate"
pip install -r "requirements.txt" --upgrade --upgrade-strategy "eager"
python3 "main.py"
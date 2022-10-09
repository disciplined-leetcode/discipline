# TODO test it
mkdir disciplined-leetcode
cd disciplined-leetcode/
git clone https://github.com/disciplined-leetcode/discipline.git
cd discipline/
echo "alias v=vim" > ~/.bashrc
# Paste/update special files
v private.py
v prod.env
sudo apt-get update
sudo apt install python3-pip
pip3 install pipenv
pipenv install
# Paste the following to ~/.bashrc
# PYTHON_BIN_PATH="$(python3 -m site --user-base)/bin"
# PATH="$PATH:$PYTHON_BIN_PATH"
source ~/.bashrc
v ~/.bashrc
pipenv install
pipenv shell
export DISCIPLINE_MODE=prod && nohup python -u discipline_bot.py > console.log 2>&1 &
tail -F console.log

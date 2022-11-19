# Installation
`pipenv install`
Install [git-crypt](https://github.com/AGWA/git-crypt/blob/master/INSTALL.md)

# Run
```Bash
pipenv shell
# For local run
git-crypt unlock <path-to-the-secret-key>
python discipline_bot.py
# For remote run
nohup python discipline_bot.py > console.log 2>&1 &
```

# discipline
[Join the Discord server](https://discord.gg/m5tS4dgg)

The bot responsible for removing user access

## Roadmap
### discipline bot
This bot. There are a lot of TODOs in [the code](discipline_bot.py) you could contribute! We could pay you too!

### redeem bot
If anyone makes a donation and they do not have the Active role
    give them the role such that they have the full access to all channels

Other potential ways of redemption. One example might be consecutively doing problems on time for 5 days.

### notification bot
We need a bot to send the question(s) of the day.

### (later) leaderboard bot
Similar to streak Timecounter https://github.com/Study-Together-Org/time_counter

## Support the server
<a href="https://www.buymeacoffee.com/Zackhardtoname" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

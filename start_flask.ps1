$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Start-Process python -ArgumentList "-X","utf8","ads_manager.py" -WorkingDirectory $dir -WindowStyle Hidden

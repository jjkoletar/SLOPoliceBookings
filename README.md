SLO Booking Log Notifications
-----------------------------

Just a little script I wrote when I discovered the [San Luis Obispo County Sheriff's Office Booking Log](http://www.slosheriff.org/WebLogs/BookingLog/BookingLog.html).

It sends email notifications detailing who's been arrested by UPD.

# Setup
```
pip install requests
pip install beautifulsoup4
pip install lxml
pip install pyzmail
```

# `subscribers` file format
```
Jeremy: jjkoletar@nowhere.com
```

# `aws_credentials` file format
```
AWS_KEY_ID:AWS_SECRET_KEY
```

import requests
import os.path
import pickle
import pyzmail
from bs4 import BeautifulSoup

CHARGES = {
    # California Business & Professional Code
    "25662(A) BP": "Minor in Possession",

    # California Health & Safety Code
    "11350 HS": "Possession of a Controlled Substance",

    # California Penal Code
    "647(F) PC": "Drunk in Public",
    "69 PC": "Resisting an Officer",
    "148(A)(1) PC": "Obstruction of Justice",
    "978.5 PC": "Failure to Appear",
    "290.011(A) PC": "Failure to Register as a Sex Offender",
    "1203.2 PC": "Violation of Probation",

    # California Vehicle Code
    "23152 VC": "DUI (general)",
    "23152(A) VC": "DUI (alcohol)",
    "23152(B) VC": "DUI, >0.08 BAC",
    "23152(E) VC": "DUI (drug)",
    "23224(A) VC": "Minor Driving w/Alcohol",
    "22450 VC": "Failure to Stop at a Stop Sign",
}

SUBSCRIBERS = {}
with open("subscribers", "r") as subscribers:
    while True:
        line = subscribers.readline()
        if not line: break
        name, email = line.strip().split(": ")
        SUBSCRIBERS[name] = email

logData = requests.get("http://www.slosheriff.org/WebLogs/BookingLog/Data/WebBookingLog.xml").text

tree = BeautifulSoup(logData, "lxml-xml")

charges = tree.findAll(Agency="CPPD")

if not os.path.isfile("previous_bookings"):
    # Skip unpickling the old set and just establish an empty one
    previousBookings = set()
else:
    # Unpickle the old bookings.
    pbfile = open("previous_bookings", "r")
    previousBookings = pickle.load(pbfile)
    pbfile.close()

updCharges = tree.findAll(Agency="CPPD")
newBookings = []
for charge in updCharges:
    # Is this a known booking, or a novel booking?
    bookingNo = charge.parent.get("bookingNo")
    if bookingNo in previousBookings:
        # Seen it.
        continue

    # So we've got a new charge, at least.
    # Add it to the newBookings list if it's not already there.
    # I could use a set, but this way we keep the order intact from the booking log,
    # which is already sorted.
    if charge.parent not in newBookings:
        newBookings += [charge.parent]

notifyList = []
newCharges = set()

for booking in newBookings:
    # Process each newBooking into an ASCII summary for the notif email.
    str =  booking.get("date") + "\n"
    str += "%s - %s y/o %s, DOB %s\n" % (booking.get("name"), booking.get("age"), booking.get("sex"), booking.get("dob"))
    str += "--> Charged with:\n"
    for charge in booking.findAll("Charge"):
        code = charge.get("ViolationCode")
        if code not in CHARGES:
            newCharges.add(code)
        str += "  * %s (%s)\n" % (CHARGES.get(code, "Unknown"), code)
    if booking.ScheduledEvent:
        type = booking.ScheduledEvent.get("type")
        # Make the caps work on the event type.
        type = type[0] + type[1:].lower()
        str += "%s Date: %s\n" % (type, booking.ScheduledEvent.get("date"))
    notifyList += [str]


if newCharges:
    str = "New Charges: " + ", ".join(newCharges)

if not notifyList:
    # Nothing new today. Don't bother people with an email.
    print "Nothing new."
    exit(0)

sender = ('UPD Bot', 'noreply@jjkoletar.com')
recipients = SUBSCRIBERS.items()
subject = u'UPD Booking Log'
text_content = "\n\n".join(notifyList)
prefered_encoding='iso-8859-1'
text_encoding='iso-8859-1'

payload, mail_from, rcpt_to, msg_id=pyzmail.compose_mail(
    sender,
    recipients,
    subject,
    prefered_encoding,
    (text_content, text_encoding))


smtp_host = "email-smtp.us-east-1.amazonaws.com"
smtp_port = 587
smtp_mode = "tls"
with open("aws_credentials", "r") as creds:
    smtp_login, smtp_password = creds.read().strip().split(":")

ret = pyzmail.send_mail(payload, mail_from, rcpt_to, smtp_host,
    smtp_port=smtp_port, smtp_mode=smtp_mode,
    smtp_login=smtp_login, smtp_password=smtp_password)

if ret == {}:
    print "All good."
else:
    print "Some kind of error: " + ret
    # Exit now, because we failed to actually send people the updates
    # for the new bookings.
    exit(1)

# Finally, time to update the previous bookings set.
for booking in newBookings:
    previousBookings.add(booking.get("bookingNo"))

pbfile = open("previous_bookings", "w")
pickle.dump(previousBookings, pbfile)
pbfile.close()

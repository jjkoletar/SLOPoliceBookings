import requests
import os.path
import pickle
import pyzmail
import subprocess
from bs4 import BeautifulSoup

# Shout-out to the very helpful Sergeant Tony Perry of the SLO County Sheriff's Office for
# his help decoding the agency codes.
AGENCIES = {
    "AGPD": "Arroyo Grande PD",
    "ASHP": "??",
    "ATPD": "Atascadero PD",
    "BAIL": "??Court Bailiffs?",
    "CAPO": "California Department of Parks and Recreation: Oceano",
    "CAPR": "California Department of Parks and Recreation: San Luis Obispo",
    "CHPD": "CHP Coastal Division Headquarters",
    "CHPS": "CHP San Luis Obispo",
    "CHPT": "CHP Templeton",
    "CMC":  "??",
    "COURT":"??",
    "CPPD": "Cal Poly University PD",
    "DA":   "District Attorney",
    "GBPD": "Grover Beach PD",
    "MBPD": "Morro Bay PD",
    "OTHR": "Other Agency",
    "PBPD": "Pismo Beach PD",
    "PROB": "SLO Probation Officers",
    "PRPD": "Paso Robles PD",
    "SLPD": "San Luis Obispo PD",
    "SLSO": "San Luis Obispo County Sheriff's Office",
    "SPAR": "??",
}

CHARGES = {
    # California Business & Professional Code
    "25661(A) BP": "Minor in Possession of a False ID",
    "25662(A) BP": "Minor in Possession",

    # California Health & Safety Code
    "11350 HS": "Possession of a Controlled Substance",
    "11357(B) HS": "Possession of <1 oz Marijuana",
    "11364(A) HS": "Possession of Paraphernalia",
    "11377(A) HS": "Misdemeanor - Possession of a Controlled Substance",
    "11550 HS": "Use/Under Influence of Controlled Substance",
    "11550(A) HS": "Under the Influence of a Controlled Substance",

    # California Penal Code
    "69 PC": "Resisting an Officer",
    "148(A) PC": "Obstructs/Resists Public Officer, etc.",
    "148(A)(1) PC": "Resisting Arrest/Obstruction of Justice",
    "148.9(A) PC": "False Identification to Peace Officer",
    "166(C)(4) PC": "Violation of Protective Order w/Prior",
    "186.22(A) PC": "FELONY - PARTICIPATE IN CRIMINAL STREET GANG",
    "243(B) PC": "BATTERY ON PEACE OFFICER/EMERGENCY PERSONNEL/ETC",
    "243(D) PC": "Battery w/Serious Injury",
    "245(A)(1) PC": "FELONY - ASSAULT W/DEADLY WEAPON OTHER THAN FIREARM OR GBI",
    "272(A)(1) PC": "Contribute to the Deliquency of a Minor",
    "273.5 PC": "INFLICT CORPORAL INJURY ON SPOUSE/COHABITANT",
    "290.011(A) PC": "Failure to Register as a Sex Offender",
    "311.11(A) PC": "OBS - POSSESS/ETC MATTER DEPICTING MINOR UNDER 14 IN SEX",
    "368(B)(1) PC": "Felony Elder Abuse w/GBI",
    "459 PC": "Burglary",
    "484(A) PC": "Petty Theft/Larceny",
    "496D(A) PC": "FELONY - VEH/TRAILER CONST EQUIP KNOWN TO BE STOLEN",
    "537E(A) PC": "MISDEMEANOR - BUY/SELL ARTICLES WITH IDENTIFICATION REMOVED",
    "647(F) PC": "Drunk in Public",
    "664/211 PC": "Attempted Robbery",
    "853.8 PC": "Failure to Appear (Promise to Appear)",
    "978.5 PC": "Felony Failure to Appear (Bench Warrant)",
    "1203.2 PC": "Violation of Probation",
    "1203.2(A) PC": "Revocation of Probation Rearrest",
    "3056 PC": "Violation of Parole",
    "3455(A) PC": "Violation of Post Release Supervision",
    "3455(B)(1) PC": "Violation of Post Release Community Supervision",
    "4573 PC": "Bringing Narcotics to a Prisoner",
    "4574(A) PC": "WEAPON/TEAR GAS OFFENSE:PRISON/JAIL/ETC",
    "29800(A)(1) PC": "Felon in Possession of a Firearm",

    # California Vehicle Code
    "5200 VC": "Display of License Plates",
    "10851(A) VC": "FELONY - AUTO THEFT, PERMNNTLY/TEMP DEPRIVE OWNER OF POSS",
    "12500(A) VC": "Driving w/o a License",
    "14601.1(A) VC": "Driving w/Suspended License",
    "14601.2(A) VC": "Driving w/Suspended License, Under The Influence related",
    "20002(A) VC": "HIT-RUN, PROPERTY DAMAGE, INCLUDING VEHICLES",
    "22450 VC": "Failure to Stop at a Stop Sign",
    "23152 VC": "DUI (general)",
    "23152(A) VC": "DUI (alcohol)",
    "23152(B) VC": "DUI, >0.08 BAC",
    "23152(E) VC": "DUI (drug), first offense",
    "23224(A) VC": "Minor Driving w/Alcohol",
    "22349(A) VC": "Exceeding the Posted Speed Limit",
    "40515 VC": "Failure to Appear wrt Promise to Appear/Continuance",
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
    notifyList += [str]

if not notifyList:
    # Nothing new today. Don't bother people with an email.
    print "Nothing new."
    exit(0)

if len(SUBSCRIBERS) == 0:
    print "\n\n".join(notifyList)
    exit(0)

# Make a datestamp using /bin/date. Sue me :)
binDate = subprocess.Popen(['date', '+%m/%d/%Y'], stdout=subprocess.PIPE)
datestamp, _ = binDate.communicate()

sender = ('UPD Bot', 'noreply@jjkoletar.com')
recipients = SUBSCRIBERS.items()
subject = u'UPD Booking Log for %s' % datestamp.strip()
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

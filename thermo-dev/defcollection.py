#!/usr/bin/python

from datetime import  datetime, timedelta
import urllib, smtplib, re
from email.mime.text import MIMEText

path = '/home/pi/thermo-dev/log/'

def decodeposteddict(data_posted): #decodes an (urllib.urlencod())ed dictionary
    data = {}
    for posts in data_posted.split('&'):
        foo=urllib.unquote(posts).split('=')
        data.update({foo[0]: foo[1]})

    return data


def post2dict(post):
    foo = {}
    for keys in post.keys():
        foo.update({keys: post.getvalue(keys)})
    return foo


def logme(line, logfile = path + './verbose.log'):
    with open(logfile, 'ab') as f:
        logline = datetime.utcnow().strftime('%a,%d.%m/%R') + ' | ' + str(line) + '\n'
        try:
            f.write(logline)
        except:
            f.write(line)

###############################################
def validate_dbpost(post):
    for keys in post:
        for chars in keys:
            if chars != '$':
                pass
            else:
                raise CustomException("Illegal insert into db: " + repr(keys))
            
##################################################            
class CustomException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)
    
##########################################################################3
def sendreport(repmail, msgsubject, msgbody):
    if type(msgbody) == dict:
        msgbody = '\n'.join([key+': '+repr(msgbody[key]) for key in msgbody]) ## repr causes /n/r in contact-form...

    msg = MIMEText(msgbody.encode('utf-8'), 'plain', 'utf-8')  # http://bugs.python.org/issue1368247
    msg['From']='Klery Studios'
    msg['to']=repmail
    msg['Subject']=msgsubject
    server = smtplib.SMTP('smtp.gmail.com')
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login('robot@klerystudios.gr', '')
    server.sendmail(repmail, [repmail], msg.as_string())
    server.quit()
    
#######################################################################33
# http://code.activestate.com/recipes/66439-stringvalidator/
class StringValidator:
	RE_ALPHA = None
	RE_ALPHANUMERIC = None
	RE_NUMERIC = None
	RE_EMAIL = None

	validateString = ""
        _patterns = {}

	def __init__(self, validateString):
		self.validateString = validateString

	def isAlpha(self):
                if not self.__class__.RE_ALPHA:
                        self.__class__.RE_ALPHA = re.compile("^\D+$")
                return self.checkStringAgainstRe(self.__class__.RE_ALPHA)

	def isAlphaNumeric(self):
                if not self.__class__.RE_ALPHANUMERIC:
                        self.__class__.RE_ALPHANUMERIC = re.compile("^[a-zA-Z0-9]+$")
                return self.checkStringAgainstRe(self.__class__.RE_ALPHANUMERIC)

	def isNumeric(self):
                if not self.__class__.RE_NUMERIC:
                        self.__class__.RE_NUMERIC = re.compile("^\d+$")
                return self.checkStringAgainstRe(self.__class__.RE_NUMERIC)

	def isEmail(self):
                if not self.__class__.RE_EMAIL:
                        self.__class__.RE_EMAIL = re.compile("^.+@.+\..{2,3}$")
                return self.checkStringAgainstRe(self.__class__.RE_EMAIL)

	def isEmpty(self):
		return self.validateString == ""

        def definePattern(self, re_name, re_pat):
                self._patterns[re_name] = re_pat

        def isValidForPattern(self, re_name):
                if self._patterns.has_key(re_name):
                        if type(self._patterns[re_name]) == type(''):
                                self._patterns[re_name] = re.compile(self._patterns[re_name])
                                return self.checkStringAgainstRe(self._patterns[re_name])
                else:
                        raise KeyError, "No pattern name '%s' stored."

	# this method should be considered to be private (not be be used via interface)

	def checkStringAgainstRe(self, regexObject):
            try:
		if regexObject.search(self.validateString) == None:
			return False
	    except TypeError:
                return False
	    return True

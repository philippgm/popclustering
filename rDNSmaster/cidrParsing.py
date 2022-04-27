import re
import pycurl,socket,struct,math,time,sys
from netmiko import ConnectHandler
from io import BytesIO
# from dns import resolver

#This takes in an integer value ASN and returns the HTML of the
# cidr-report for the ASN as a string.
def rxASN(asn):
	url = 'http://www.cidr-report.org/cgi-bin/as-report?as=' + str(asn) + '&view=2.0'
	page = BytesIO()
	site = pycurl.Curl()
	site.setopt(site.URL, url)
	site.setopt(site.WRITEDATA, page)
	site.perform()
	site.close()
	
	return(page.getvalue().decode('ISO-8859-1'))
	#page.readline()
	#return(page)
   
#This function takes in the HTML of a web page as a StrinIO object and parses it for
#networks.  The return value of the function is a list of the NLRIs in
#the NET/CIDR format.
def parseASN(asnPage):
	prefixesFound = 0
	fragmentsFound = 0
	cidrList = []
	tmpCidrList = []
	
	# print(asnPage)
	for line in asnPage.splitlines():
		try:
			if re.search("^Prefix ",line.lstrip()):
				prefixesFound = 1
			elif line.split()[0] == "Advertisements":
				prefixesFound = 0
				fragmentsFound = 1
			elif re.search('added and withdrawn|whois',line.lower()):
				fragmentsFound = 0
		except IndexError:
			pass
		if prefixesFound and re.search("black|green",line):
			prefix = re.findall("[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}/[\d]{1,2}",line)[0]
			if prefix not in cidrList:
				cidrList.append(prefix)
		elif fragmentsFound:
			try:
				tmpCidrList = re.findall("[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}/[\d]{1,2}",line)
				cidrList.remove(tmpCidrList[0])
				if tmpCidrList[1] not in cidrList:
					cidrList.append(tmpCidrList[1])
			except IndexError:
				pass
			except ValueError:
				pass
	return(cidrList)

def to_string(ip):
	return ".".join(map(lambda n: str(ip>>n & 0xFF), [24,16,8,0]))

def convertPrefix(prefix):
	nlri,cidr = prefix.split('/')
	return(nlri + " " + to_string(pow(2,32 - int(cidr))-1))

def checkDuplicate(p1, p2):
	# get the IP bytes and prefix number
	i1 = p1.split("/")[0].split(".")
	r1 = int(p1.split("/")[1])
	i2 = p2.split("/")[0].split(".")
	r2 = int(p2.split("/")[1])
	# convert i1 into a 32 bit integer
	ii1 = 0
	for i, b in enumerate(i1):
		ii1 = ii1 + int(b)*(2**(8*(len(i1)-(i+1))))
	# convert i2 into a 32 bit integer
	ii2 = 0
	for i, b in enumerate(i2):
		ii2 = ii2 + int(b)*(2**(8*(len(i2)-(i+1))))
	# set r = min(r1, r2)
	r = min(r1, r2)
	# create a mask to get only the most significant r bits only
	mask = 0
	for i in range(0, r):
		m = 1 << (31-i)
		mask |= m
	ii1m = ii1 & mask
	ii2m = ii2 & mask
	# check if p2 is a subnet of p1
	if (ii1m == ii2m):
		# print("------")
		# print("{0:b}".format(mask))
		# print(".".join(i1) + "/" + str(r1))
		# print("{0:b}".format(ii1))
		# print("{0:b}".format(ii1m))
		# print(".".join(i2) + "/" + str(r2))
		# print("{0:b}".format(ii2))
		# print("{0:b}".format(ii2m))
		if r == r1:
			return p2
		if r == r2:
			return p1
	else:
		return None

def checkDuplicates(prefixes):
	for p1 in prefixes:
		for p2 in prefixes:
			if (p1 != p2):
				rmvprefix = checkDuplicate(p1, p2)
				if rmvprefix:
					# print("Removing " + rmvprefix)
					if rmvprefix in prefixes:
						prefixes.remove(rmvprefix)
	return prefixes

# def main():
#	 asn = int(sys.argv[1])
#	 page = rxASN(asn)
#	 prefixes = parseASN(page)
#	 print(prefixes)
#	 for p1 in prefixes:
#		 for p2 in prefixes:
#			 if (p1 != p2):
#				 rmvprefix = checkduplicate(p1, p2)
#				 if rmvprefix:
#					 print("Removing " + rmvprefix)
#					 prefixes.remove(rmvprefix)

# if __name__ == "__main__":
#	 main()

__author__ = 'nick'
__version__ = 1

import os
import hashlib
import MySQLdb
import urllib2
import sys
import csv

## Set some global variables
def setOperationVars():

	# MySQL and InShape logins
	global MySQL_user, MySQL_pass, InShape_pass, InShape_user
	InShape_user = 'nickjanssen'
	InShape_pass = 'sh4pew4ysJOB14'
	MySQL_user = 'nick'
	MySQL_pass = 'iawoch3Wai'



	# Get scripts file path
	global curDir, traysDir
	curDir = os.path.dirname(__file__)
	print "Workingdirectory: " + curDir

	# Check if tray folder exist
	traysDir = curDir + "/trays/"
	try:    os.stat(traysDir)
	except: os.mkdir(traysDir)




	# Query to select the tray properties
	global  queryPOData
	queryPOData = """
   select pt.display_name          tray_name
        , po.production_order_name po_name
        , po.order_item_id         oi_id
        , po.quantity              quantity
        , oi.order_id              o_id
        , om.model_id              m_id
        , om.model_version         m_ver
        , mpf.model_part_file_id   mpf_explode_id
        , mpf_m.model_part_file_id mpf_multipart_id

        , if (om.parts = 1, om.printer_model_location, if(po.model_part_file_id, mpf.printer_model_location, mpf_m.printer_model_location)) mpf_file

        , @volume     := IFNULL(mpf.volume, om.volume)          vol
        , @volume_xsf := IFNULL(mpf.volume_xsf, om.volume_xsf)  vol_xsf
        , @surface    := IFNULL(mpf.area, om.area)              surf
        , @width      := IFNULL(mpf.maxx - mpf.minx, om.width)  w
        , @height     := IFNULL(mpf.maxy - mpf.miny, om.height) h
        , @depth      := IFNULL(mpf.maxz - mpf.minz, om.depth)  d
        , (@width * @height * @depth ) AS                       vol_bb
     from production_order po
     join order_item oi
       on po.order_item_id = oi.order_item_id
     join order_model om
       on oi.item_id = om.order_model_id
      and oi.order_item_type_id in (1,4,5)
     join production_tray pt
       on po.production_tray_id = pt.production_tray_id
left join model_part_file mpf
       on mpf.model_part_file_id = po.model_part_file_id
left join model_part_file mpf_m
       on po.model_part_file_id is null
      and om.parts <> 1
      and po.order_item_id = mpf_m.order_item_id
    where po.production_tray_id IN
  (SELECT pt.production_tray_id
     FROM production_tray pt
    WHERE pt.name RLIKE '%s')""" # by Barry on 150828, SELECT variables and tray select added by Nick 150829

	print "Login into MySQL DB as user \"%s\"" %(MySQL_user)
	global myDB
	myDB = MySQLdb.connect(host="rodb2-nyc.nyc.shapeways.net",
						   port=3306,
						   user=MySQL_user,
						   passwd=MySQL_pass,
						   db="udesign")




def getPartsInfoFromDb(trayName):
	print "\t\tExecuting tray query"
	handleQuery = myDB.cursor()
	handleQuery.execute( queryPOData%(trayName) )

	#Get database data
	trayData = handleQuery.fetchall()

	#Create blank matrix to hold processed data
	print "\t\tReduce query results to return Single Part Files"
	SPFListData = []
	for SPF in trayData:
		#Add row to blank data matrix
		SPFListData.append(SPFDataCont( SPF[4], SPF[5], SPF[9]) )
	myDB.close()
	handleQuery.close()
	
	return SPFListData, trayData


class SPFDataCont:
	o_id = 0
	m_id = 0
	mpf_file = ""

	def __init__(self,*args):
		self.o_id = args[0]
		self.m_id = args[1]
		self.mpf_file = args[2]

def downloadSPF(SPFData):

	# Generate hastag
	hash = hashlib.md5()
	hash.update('hjGhfHJI&54sdf')
	hash.update(str(SPFData.o_id))
	hash.update(str(SPFData.m_id))

	# Build URL to file
	strUrlRequest = "http://netfabb.ehv.shapeways.net/server/40495/?proc=download&key=8afdef591d5511e2b6b4001ec9eb08bb&"+\
		"orderId=%d&modelId=%d&fileName=%s&hash=%s" %(SPFData.o_id, SPFData.m_id, SPFData.mpf_file, hash.hexdigest() )

	# Open connection and get file info
	fileLink = urllib2.urlopen(strUrlRequest)

	print "\t\t\t\"%s\"" %(SPFData.mpf_file)
	fileData = fileLink.read()


	if len(fileData) <= 300:
		if fileData.find("invalid parameter"):
			print >> sys.stderr, 'Err: File \"%s\" not found: wrong parameters given!!'%(SPFData.mpf_file)
			exit(0)
		if len(fileData) == 0:
			print >> sys.stderr, 'Err: File \"%s\" is 0 bytes!'%(SPFData.mpf_file)
			exit(0)
	else:
		return fileData




def processTrayList(trayList):
	print "Start processing tray(s)"

	# Loop through trays
	for trayName in trayList:
		print "\tProcessing tray \"%s\"" %(trayName)

			# Check if tray folder exist
		trayDir = traysDir + trayName + "/"
		try:    os.stat(trayDir)
		except: os.mkdir(trayDir)
	
		# Get the parts in the current tray
		print "\tGet SPF information from DB"
		SPFListData, trayData = getPartsInfoFromDb(trayName)
		traySPFDataFile = trayDir + trayName + '_SPFData.csv'
			
		print "\tPut SPF date into file \"%s\"" %(traySPFDataFile)
		fp = open(traySPFDataFile, 'wb')
		myFile = csv.writer(fp)
		myFile.writerows(trayData)
		fp.close()

		i = 1
		print "\tDownload tray"
		for SPFData in SPFListData:
						# Check file existence
			if os.path.isfile(trayDir + SPFData.mpf_file):
				print "\t\tSPF %i of %i already present" %(i, SPFListData.__len__() )
				i = i + 1
				continue

			print "\t\tDownload SPF %i of %i" %(i, SPFListData.__len__() )
			fileData = downloadSPF(SPFData)

			print "\t\tSave SPF to local folder"
			fileHandler = open(trayDir + SPFData.mpf_file , 'wb')
			fileHandler.write( fileData )
			fileHandler.close()

			i = i + 1

		print "Tray \"%s\" done" %(trayName)


	print "All tray(s) done"

	return




# Process everything
setOperationVars()

#partList = getPartsInfoFromDb('2015030.[SML][1-3].*')
trayList = ['20150829S1']
processTrayList(trayList)

print "Done"





# traySt ring = '2015030.[SML][1-3].*'
# getPartsInfoFromDb(trayName)
#'20150328l2', '1902473-2', '3', NULL, '2388102', '927587', '2949987', '2', '123154', '123154'


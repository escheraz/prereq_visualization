import networkx as nx
import matplotlib.pyplot as plt
import urllib.request, urllib.error, urllib.parse

def getScrapeRequest():
	"""
	Returns the scraping request.
	"""
	majorNums = {3,5,18}
	majorNums = {1,2,3,4,5,6,7,8,9,10,11,12,14,15,16,17,18,20,22,24} #Course 21 and non-numeric courses skipped

	numPages = dict() #The number of course catalog pages each major has
	for i in {1,2,6,11,12,15,22}:
		numPages[i] = 3
	for i in {3,5,8,9,10,14,16,17,18,24}:
		numPages[i] = 2
	for i in {7,20}:
		numPages[i] = 1
	numPages[4] = 6
	return (majorNums, numPages)

def getHTMLPage(majorNum, pageNum):
	"""
	Scrapes the requisite page and downloads the HTML page into a bytestring.
	"""
	url = f"http://student.mit.edu/catalog/m{majorNum}{chr(97 + pageNum)}.html"
	print(url)
	response = urllib.request.urlopen(url)
	return str(response.read())

def scrapeData(majorNums, numPages):
	"""
	Downloads all the relevant HTML pages into a concatenation in a dictionary indexed by major number
	"""
	majorPages = {}
	for majorNum in majorNums:
		majorPages[majorNum] = []
		page = ""
		for pageNum in range(numPages[majorNum]):
			page += getHTMLPage(majorNum, pageNum)
		majorPages[majorNum] = page
	return majorPages

def getCourseNums(majorNums, majorPages):
	"""
	Makes a set containing all Course Numbers.
	"""
	courseNums = set()
	for majorNum in majorNums:
		courses = [x[:x.index('"')] for x in majorPages[majorNum].split('<a name="')[1:]]
		for course in courses:
			courseNums.add(course)
	return courseNums

def removeSpecialSubjects(courseNums):
	"""
	Returns a set of course numbers without letters in their name
	"""
	courseNumsNoSpecials = set()
	for course in courseNums:
		if any(char in course for char in 'QWERTYUIOPASDFGHJKLZXCVBNM'):
			continue
		courseNumsNoSpecials.add(course)
	courseNumsNoSpecials.add('18.100') #special case - central subject in math department, but offered in 4 versions, so combine here
	return courseNumsNoSpecials

def processPrereqHTML(text):
	"""
	Remove html tags from a string, then returns list of numbers of either coreqs/prereqs
	HTML tag stripping taken from https://medium.com/@jorlugaqui/how-to-strip-html-tags-from-a-string-in-python-7cb81a2bbf44
	"""
	import re
	clean = re.compile('<.*?>')
	text = re.sub(clean, '', text)
	text = text.replace('Prereq:', '') \
				.replace('Coreq:', '') \
				.replace(';', '') \
				.replace('Ceq', '') \
				.replace('None.', '') \
				.replace(':', '') \
				.replace('and', '') \
				.replace('or', '') \
				.replace('(', '') \
				.replace(')', '') \
				.replace('permission of instruct', '') \
				.replace('Permission of instruct', '') #ors already excised here 
	text = text.strip().replace(',', ' ').replace('  ', ' ').replace('  ', ' ')
	#use synonyms for GIR requirements, corresponding to the most-taken variant.
	#18.100 variants are all coalesced into 18.100; all courses that require 18.100 as prereq accept all versions
	text = text.replace('Chemistry GIR', '5.111') \
			.replace('Calculus I GIR', '18.01') \
			.replace('Physics I GIR', '8.01') \
			.replace('Physics II GIR', '8.02') \
			.replace('Calculus II GIR', '18.02') \
			.replace('Biology GIR', '7.012') \
			.replace('18.100A', '18.100')
	if text == "":
		return []
	else:
		print(text)
		return text.split()

def getPrereqs(HTMLpage, courseNum):
	"""
	Returns a list of prereqs of a given course number
	"""
	if courseNum == '18.100':
		return ['18.02'] #18.100 manually coded in since it's not a real course, but is important enough to the course 18 program to be included manually

	idx = HTMLpage.index(f'<a name="{courseNum}">')
	if idx == -1:
		print(f'could not get prereqs on {courseNum}!')
	HTMLpage = HTMLpage[idx:]
	HTMLpage = HTMLpage[HTMLpage.index('Prereq: '):]
	prereqHTML = HTMLpage[:HTMLpage.index('\\n')]	
	return processPrereqHTML(prereqHTML)
	#Currently nonexistent courses that are listed as prereqs on catalog: 3.022, 3.024, 9.16, 15.810

def getAllPrereqs(courseNums, majorPages):
	"""
	Returns a dictionary mapping course numbers to their prereqs
	"""
	prereqs = {}
	for course in courseNums:
		prereqs[course] = getPrereqs(majorPages[int(course[:course.index('.')])], course)
	return prereqs

def generateTotalGraph(courseNums, prereqs):
	"""
	Generates the entire graph of prereq-requirements, with a few modificatinos to make
	distinct connected components for each major.
	"""
	G = nx.DiGraph()
	G.add_nodes_from(courseNums)
	for course in courseNums:
		addNone = 0
		for prereq in prereqs[course]:
			if prereq not in courseNums:
				print(f"Course {prereq} not found for course {course}")
			else:
				if prereq[:prereq.index('.')] == course[:course.index('.')]:
					addNone = 1
					G.add_edge(prereq, course)
				else:
					G.add_edge(course[:course.index('.')] + '.' + prereq.replace('.','-'), course) #Need to separate prereqs if they are out-of-department or a very hard to analyze highly connected graph will be created. For example, 18.03 being required for course 5 would be written as 5.18-03. Will be reverted back later.
		if addNone == 0:
			G.add_edge(course[:course.index('.')] + '.NONE', course) #XX.NONE represents that we have no prerequisites from department XX; this serves to connect all these courses together into one connected component
	return G

def writeGraph(G, majorNums):
	"""
	Takes in the output from generateTotalGraph and writes xml files for each major that contain their class networks.
	"""
	print(nx.number_weakly_connected_components(G)) #separate graph into its weakly connected components, allows for easier rendering (though makes 20 xml graph files)
	for component in nx.weakly_connected_components(G):
		for majorNum in majorNums: #This is a bit inefficient, but it works out fine
			if f'{majorNum}.NONE' in component:
				sg = G.subgraph(component).copy()
				relabeling = {}
				for node in component:
					if '-' in node:
						relabeling[node] = node.replace('-', '.')[node.find('.')+1:] #now that we have subgraphs, we can use the standard name of these non-departmental courses
				print(relabeling)
				sg = nx.relabel_nodes(sg, relabeling)
				nx.write_graphml(sg, f'Course {majorNum}.xml')	

majorNums, numPages = getScrapeRequest()
majorPages = scrapeData(majorNums, numPages)
courseNums = removeSpecialSubjects(getCourseNums(majorNums, majorPages))
prereqs = getAllPrereqs(courseNums, majorPages)
totalGraph = generateTotalGraph(courseNums, prereqs)
writeGraph(totalGraph, majorNums)


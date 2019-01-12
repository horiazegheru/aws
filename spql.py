import json, os, urllib, traceback, requests, sys
from flask import Flask, render_template, request, session
app = Flask(__name__)

#Some sample query.
query_string = """ 
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>

SELECT DISTINCT ?s ?label ?syn
WHERE {
	   ?s a owl:Class .
	   ?s rdfs:label ?label .
	   ?s oboInOwl:hasExactSynonym ?syn .
}
"""

def query(q,apikey,epr,f='application/json'):
	"""Function that uses urllib/urllib.request to issue a SPARQL query.
	   By default it requests json as data format for the SPARQL resultset"""

	try:
		params = {'query': q, 'apikey': apikey}
		params = urllib.parse.urlencode(params)
		opener = urllib.request.build_opener(urllib.request.HTTPHandler)
		request = urllib.request.Request(epr+'?'+params)
		request.add_header('Accept', f)
		request.get_method = lambda: 'GET'
		url = opener.open(request)
		return url.read()
	except Exception as e:
		traceback.print_exc(file=sys.stdout)
		raise e

def insert(has_exact_syn, ro_syn):
	insert_string = """
		PREFIX owl:  <http://www.w3.org/2002/07/owl#>
		PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
		PREFIX purl: <http://www.purl.org/>
		prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
	    prefix purlObo: <http://purl.obolibrary.org/obo/doid.owl#>

	    DELETE { ?class purlObo:ro_translation ''}
		INSERT { ?class purlObo:ro_translation '%s' }
		WHERE
		  { ?class oboInOwl:hasExactSynonym '%s' .
		  } 
		""" % (ro_syn, has_exact_syn.replace("'", "\\'"))
	q = {"update": insert_string}
	json_string = requests.post(update_service, q)
	return str(json_string) + ": " + has_exact_syn + " = " + ro_syn

def query_by_contains_name(disease_name_ro):
	return """ 
	PREFIX owl:  <http://www.w3.org/2002/07/owl#>
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
	PREFIX purl: <http://www.purl.org/>
	PREFIX obo: <http://purl.obolibrary.org/obo/>
	prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
	prefix purlObo: <http://purl.obolibrary.org/obo/doid.owl#>

	SELECT DISTINCT ?s ?label ?trans ?symptom
	WHERE {
		   ?s a owl:Class .
		   ?s rdfs:label ?label .
  		   ?s purlObo:ro_translation ?trans .
		   ?s obo:IAO_0000115 ?symptom .
  			FILTER regex(?trans, "%s", "i" ) 
	}
	""" % disease_name_ro

def query_by_contains_name_en(disease_name_en):
	return """ 
		PREFIX owl:  <http://www.w3.org/2002/07/owl#>
		PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
		PREFIX purl: <http://www.purl.org/>
		PREFIX obo: <http://purl.obolibrary.org/obo/>
		prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
		prefix purlObo: <http://purl.obolibrary.org/obo/doid.owl#>

		SELECT DISTINCT ?s ?label ?trans ?symptom
		WHERE {
			   ?s a owl:Class .
			   ?s rdfs:label ?label .
	  		   ?s purlObo:ro_translation ?trans .
			   ?s obo:IAO_0000115 ?symptom .
	  			FILTER regex(?label, "%s", "i" ) 
		}
		""" % disease_name_en

@app.route('/')
def index():
	html_page = render_template("front.html")
	return html_page

@app.route("/select" , methods=['GET', 'POST'])
def select():
	disease_name = request.args.get("search_box")

	if disease_name == '':
		return render_template('error.html')

	query_string = query_by_contains_name(disease_name)
	json_string = query(query_string, "", sparql_service)
	resultset = json.loads(json_string)

	label_trans = []
	for result in resultset["results"]["bindings"]:
		label = result["label"]["value"]
		syn = result["trans"]["value"]
		symptoms = result["symptom"]["value"]

		label_trans.append((label, syn, symptoms))

	html_page = render_template("diseases_by_name.html", **{
			'query': disease_name,
			'language': 'Search was made in romanian',
			'diseases': label_trans,
	})

	return html_page

@app.route("/select_en" , methods=['GET', 'POST'])
def select_en():
	disease_name = request.args.get("search_box")

	if disease_name == '':
		return render_template('error.html')

	query_string = query_by_contains_name_en(disease_name)
	json_string = query(query_string, "", sparql_service)
	resultset = json.loads(json_string)

	label_trans = []
	for result in resultset["results"]["bindings"]:
		label = result["label"]["value"]
		syn = result["trans"]["value"]
		symptoms = result["symptom"]["value"]

		label_trans.append((label, syn, symptoms))

	html_page = render_template("diseases_by_name.html", **{
		'query': disease_name,
		'language': 'Search was made in english',
		'diseases': label_trans,
	})

	return html_page

def init():
	json_string = query(query_string, "", sparql_service)
	resultset = json.loads(json_string)
	to_translate = []

	lista = []
	label_set = set()

	for result in resultset["results"]["bindings"]:
		s = json.dumps(result["s"]["value"])
		label = result["label"]["value"]
		syn = result["syn"]["value"]

		if label not in label_set:
			to_translate.append(syn)
			lista.append([s, label, syn, ''])
			label_set.add(label)

	print(len(to_translate)) # TREBUIE SA AIBA ACEEASI LUNGIME CU CEA DE MAI JOS

	with open("sinonime.txt", 'w') as outfile:
		outfile.write(json.dumps(to_translate,indent=1))

	with open("faradiacritice", "r") as infile:
		answers = []
		romanian_translations = infile.read().split("\n")
		print(len(romanian_translations))
		for i in range(len(romanian_translations)):
			answers.append(insert(to_translate[i], romanian_translations[i]))
		with open("ans.txt", "w") as outfile:
			outfile.write(json.dumps(answers,indent=1))
			# aici doar testez sa vad ca primesc doar 200 la inserturi

if __name__ == "__main__":
	sparql_service = "http://localhost:3030/ds/query"
	update_service = "http://localhost:3030/ds/update"

	# DECOMENTEAZA CAND PORNESTI FUSEKI!
	# (de fiecare data cand porneste serverul si uploadezi boli.owl,
	# trebuie facut query-ul care scoate toate sinonimele si le
	# imperecheaza cu ce e deja tradus)

	# init()

	app.secret_key = os.urandom(12)
	app.run(debug=True)
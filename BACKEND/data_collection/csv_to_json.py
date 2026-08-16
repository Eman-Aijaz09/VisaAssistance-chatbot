import csv
import json

with open('data/germany_knowledge.csv', 'r') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    data = list(csv_reader)

with open('germany_knowledge.json', 'w') as json_file:
    json.dump(data, json_file, indent=4)
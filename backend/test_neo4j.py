from neo4j import GraphDatabase
import json

uri = "bolt://localhost:7687"
user = "neo4j"
password = "password"

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    res = session.run('''
        MATCH (c:Component)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE]->(v:Value)
        MATCH (v)-[:HAS_UNIT]->(u:Unit)
        WHERE toLower(p.name) CONTAINS "continuous drain current"
        RETURN p.name, v.value, v.condition, u.name
    ''')
    data = [dict(r) for r in res]
    
    print(f"Total Rows: {len(data)}")
    for d in data[:5]:
        print(d)
        
    print("\n\nLet's map all names!")
    res2 = session.run('MATCH (p:Parameter) RETURN p.name AS name, count(p) as cnt')
    all_names = [dict(r) for r in res2]
    print(f"Unique Param Names: {len(all_names)}")
    for d in all_names[:10]:
        print(d)

# Glossary

### Project
A workspace container representing a single link analysis investigation. It scopes and owns all entities, edges, and logs associated with the investigation.

### Entity
A node in the graph representing an observable OSINT artifact (e.g., Domain, IPAddress, Person, EmailAddress, Hash). An entity has a type, value, and key-value properties.

### Edge
A directed link between a source entity and a target entity, representing a discovered relationship or link (e.g., "resolves_to", "belongs_to").

### Transform
A plugin or built-in script that accepts an input entity and executes an enrichment task (e.g., DNS lookup, WHOIS query) to generate new entities and edges.

### Layout
A visual positioning algorithm (e.g., Force-directed, Sugiyama, Concentric) that arranges entities on the graph canvas to optimize readability and cluster recognition.

### Centrality
A mathematical score indicating the relative importance or influence of a node in the graph topology (e.g., Degree, Betweenness, Closeness, PageRank).

### Connected Component
A maximal subgraph where any two entities are connected to each other by paths, representing isolated clusters of related intelligence.

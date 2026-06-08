# OGI Built-in Transforms Reference

This document provides a comprehensive catalog of all built-in transforms available in the OpenGraph Intel (OGI) framework.

---

## Catalog of Built-in Transforms

| Class Name | Display Name | Machine Name | Description | Input Types | Output Types | Category | Settings |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CertTransparency** | Certificate Transparency Lookup | `cert_transparency` | Discovers subdomains via Certificate Transparency logs (crt.sh) | Domain | Subdomain | Certificate | None |
| **DomainToCerts** | Domain to SSL Certificates | `domain_to_certs` | Retrieves the SSL/TLS certificate for a domain and extracts certificate details | Domain | SSLCertificate, Organization | Certificate | None |
| **DomainToIP** | Domain to IP Address | `domain_to_ip` | Resolves A and AAAA records for a domain | Domain | IPAddress | DNS | None |
| **DomainToMX** | Domain to MX Records | `domain_to_mx` | Looks up MX (mail exchange) records for a domain | Domain | MXRecord | DNS | None |
| **DomainToNS** | Domain to NS Records | `domain_to_ns` | Looks up nameserver records for a domain | Domain | NSRecord | DNS | None |
| **IPToDomain** | IP to Domain (Reverse DNS) | `ip_to_domain` | Performs reverse DNS lookup on an IP address | IPAddress | Domain | DNS | None |
| **WhoisLookup** | WHOIS Lookup | `whois_lookup` | Retrieves WHOIS registration data for a domain | Domain | Organization, Person, EmailAddress | DNS | None |
| **DomainToEmails** | Domain to Email Addresses | `domain_to_emails` | Generates common email addresses for a domain after verifying MX records exist | Domain | EmailAddress | Email | None |
| **EmailToDomain** | Email to Domain | `email_to_domain` | Extracts the domain from an email address | EmailAddress | Domain | Email | None |
| **HashLookup** | Hash Lookup | `hash_lookup` | Looks up a file hash on VirusTotal for threat intelligence | Hash | Hash | Hash | `virustotal_api_key`: secret (Required) |
| **IPToASN** | IP to ASN | `ip_to_asn` | Looks up ASN and organization for an IP address via DNS query to Team Cymru | IPAddress | ASNumber, Organization | IP Intelligence | None |
| **IPToGeolocation** | IP to Geolocation | `ip_to_geolocation` | Looks up geographic location for an IP address using ip-api.com | IPAddress | Location | IP Intelligence | None |
| **LocationToGeocode** | Location to Geocode | `location_to_geocode` | Normalizes a free-text location into canonical coordinates and admin fields. | Location | Location | Location | None |
| **LocationToNearbyASNs** | Location to Nearby ASNs | `location_to_nearby_asns` | Finds nearby ASN and network presence around a location using public peering facility data. | Location | ASNumber, Network | Location | `radius_km`: integer = 25<br>`provider_timeout_seconds`: number = 8<br>`peeringdb_api_key`: secret<br>`target_datetime`: string |
| **LocationToReverseGeocode** | Location to Reverse Geocode | `location_to_reverse_geocode` | Converts coordinates into structured address components. | Location | Location | Location | None |
| **LocationToSunTimes** | Location to Sun Times | `location_to_sun_times` | Adds sunrise, sunset, twilight, and daylight context for a location and date. | Location | Location | Location | `target_datetime`: string |
| **LocationToTimezone** | Location to Timezone | `location_to_timezone` | Resolves timezone context from location coordinates. | Location | Location | Location | None |
| **LocationToWeatherSnapshot** | Location to Weather Snapshot | `location_to_weather_snapshot` | Adds weather context for a location at the observed time or now. | Location | Location | Location | `openweather_api_key`: secret (Required)<br>`target_datetime`: string |
| **PersonToUsernames** | Person to Usernames | `person_to_usernames` | Generates likely usernames from a person's name and aliases | Person | Username | People | None |
| **WebsiteToPeople** | Website to People | `website_to_people` | Finds people listed on a website's team/about pages and extracts them using OpenAI. | Domain, URL | Person | People | `openai_api_key`: secret (Required)<br>`openai_model`: select = gpt-4.1-mini<br>`max_people`: integer = 500 |
| **UsernameSearch** | Username Search | `username_search` | Checks social platforms for likely username existence using a cached site catalog | SocialMedia, Username | SocialMedia, URL | Social Media | `min_username_length`: integer = 4<br>`must_have_name`: boolean = true<br>`scan_permutations`: boolean = false<br>`max_sites`: integer = 25<br>`concurrency`: integer = 10 |
| **ContentToIOCs** | Content to IOCs | `content_to_iocs` | Extracts common indicators of compromise from Document content | Document | URL, IPAddress, Domain, EmailAddress, Hash | Web | None |
| **DomainToURLs** | Domain to URLs (robots.txt) | `domain_to_urls` | Fetches robots.txt and extracts URLs from Sitemap and Disallow directives | Domain | URL | Web | None |
| **URLToContent** | URL to Content | `url_to_content` | Fetches a URL via Playwright and extracts readable text content into a Document entity | URL | Document | Web | `max_content_chars`: integer = 12000<br>`allow_local_network`: boolean = false |
| **URLToHeaders** | URL to HTTP Headers | `url_to_headers` | Performs a HEAD request and extracts interesting HTTP headers from a URL | URL | HTTPHeader | Web | None |
| **URLToLinks** | URL to Outbound Links | `url_to_links` | Fetches a page and extracts outbound links and their domains | URL | URL, Domain | Web | None |

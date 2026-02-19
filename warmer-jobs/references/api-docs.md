Warmer Jobs API alpha docs

JavaScript must be enabled in order to use Notion.  
Please enable JavaScript to continue.

[Skip to content](https://www.notion.so/Warmer-Jobs-API-alpha-docs-2bdcf3df59e38082b703e5cb36db5d14#main)

Warmer Jobs API alpha docs

Get Notion free

Warmer Jobs API alpha docs
==========================

Warmer Jobs Search API
----------------------

Search for roles by title, seniority, location, and more.

### 1. Basic Example (JavaScript)

const response = await fetch("https://warmerjobs.com/api/v1/search", {
method: "POST",
headers: { "Content-Type": "application/x-www-form-urlencoded" },
body: new URLSearchParams({
api\_token: "YOUR\_API\_TOKEN",
job\_title: "vp sales"
"out\_of\_network[]": "true",
})
});
const data = await response.json();
console.log(data.jobs);

​

This sends the minimal request:

api\_token

+

job\_title

.

### 2. Common Search Example (JavaScript)

const params = new URLSearchParams({
api\_token: "YOUR\_API\_TOKEN",
job\_title: "customer success",
"seniority[]": "director",
"locations[]": "san francisco",
"locations[]": "new york",
"out\_of\_network[]": "true",
fetch\_unique\_company\_results: "false"
});
const res = await fetch("https://warmerjobs.com/api/v1/search", {
method: "POST",
headers: { "Content-Type": "application/x-www-form-urlencoded" },
body: params
});
const { jobs } = await res.json();
console.log(jobs);

​

### 3. “Kitchen Sink” Example (JavaScript)

This shows how to send most filters together in one request.

const params = new URLSearchParams({
api\_token: "YOUR\_API\_TOKEN",
job\_title: "software",
salary\_min: "0",
salary\_max: "500000",
experience\_min: "0",
experience\_max: "20",
fetch\_unique\_company\_results: "true",
"in\_network[]": "true",
"out\_of\_network[]": "true",
"show\_second\_degree\_contacts[]": "true"
});
// work type
["remote", "hybrid", "in\_person"].forEach(wt =>
params.append("work\_type[]", wt)
);
// seniority
[
"intern",
"entry",
"midlevel",
"senior",
"manager",
"director",
"vp",
"svp",
"c\_level"
].forEach(s => params.append("seniority[]", s));
// employment type
[
"full\_time",
"part\_time",
"contract",
"temporary",
"seasonal",
"volunteer"
].forEach(t => params.append("employment\_type[]", t));
// education level
["high\_school", "associates", "bachelors", "masters", "phd"].forEach(level =>
params.append("education\_level[]", level)
);
// visa sponsorship
["true", "false"].forEach(v =>
params.append("visa\_sponsored[]", v)
);
// industries
[
"administrative/support services",
"arts and culture",
"biotechnology",
"construction",
"consumer services",
"ecommerce",
"education",
"entertainment",
"farming/ranching/forestry",
"financial services",
"food and beverage",
"government",
"holding companies",
"hospitals/health care",
"hospitality",
"information services",
"insurance",
"legal",
"manufacturing",
"media",
"military and defense",
"nonprofit",
"oil/gas/mining",
"professional services",
"real estate",
"religious",
"retail",
"scientific/technical services",
"software/it services",
"sports/recreation",
"telecommunications",
"transportation/logistics/supply chain/storage",
"utilities",
"wholesale"
].forEach(industry =>
params.append("industries[]", industry)
);
// funding stage
[
"pre\_seed",
"seed",
"series\_a",
"series\_b",
"series\_c",
"series\_d",
"series\_e+",
"acquired",
"public",
"private\_equity",
"bootstrapped",
"nonprofit"
].forEach(stage =>
params.append("funding\_stage[]", stage)
);
const res = await fetch("https://warmerjobs.com/api/v1/search", {
method: "POST",
headers: { "Content-Type": "application/x-www-form-urlencoded" },
body: params
});
const data = await res.json();
console.log(data.jobs);

​

4. Endpoint
-----------

POST https://warmerjobs.com/api/v1/search

​

Content-Type

Content-Type: application/x-www-form-urlencoded

​

Authentication

Include your API token in the request body:

api\_token=YOUR\_API\_TOKEN

​

5. Request Parameters
---------------------

All parameters are form-encoded. Arrays are passed as repeated keys, e.g.:

seniority[]=director&seniority[]=vp

​

### 5.1 Required

| Parameter | Type | Description |
| --- | --- | --- |
| api\_token | string | Your API key. |
| job\_title | string | Role or keyword to search (e.g. "vp sales" ). |

### 5.2 Core Filters

| Parameter | Type | Example | Description |
| --- | --- | --- | --- |
| locations[] | string (repeatable) | united states , san francisco | Filters by geography. |
| seniority[] | string (repeatable) | director , vp , c\_level | Filters by seniority level. |
| in\_network[] | boolean/string | true | Include jobs where user has direct connections. |
| out\_of\_network[] | boolean/string | true | Include jobs outside the user’s network. |
| show\_second\_degree\_contacts[] | boolean/string | true | Include second-degree contact metadata. |
| fetch\_unique\_company\_results | boolean/string | true | If true , returns at most one job per company. |

Booleans are sent as strings:

"true"

or

"false"

.

### 5.3 Work Type

| Parameter | Type | Allowed Values | Description |
| --- | --- | --- | --- |
| work\_type[] | string (repeatable) | remote , hybrid , in\_person | Filters by work structure. |

Example:

work\_type[]=remote&work\_type[]=hybrid

​

### 5.4 Seniority

Canonical list:

| Parameter | Type | Allowed Values | Description |
| --- | --- | --- | --- |
| seniority[] | string (repeatable) | intern , entry , midlevel , senior , manager , director , vp , svp , c\_level | Filters by seniority. |

### 5.5 Employment Type

| Parameter | Type | Allowed Values | Description |
| --- | --- | --- | --- |
| employment\_type[] | string (repeatable) | full\_time , part\_time , contract , temporary , seasonal , volunteer | Filters by employment type. |

### 5.6 Education Level

| Parameter | Type | Allowed Values | Description |
| --- | --- | --- | --- |
| education\_level[] | string (repeatable) | high\_school , associates , bachelors , masters , phd | Minimum education requirement. |

### 5.7 Visa Sponsorship

| Parameter | Type | Allowed Values | Description |
| --- | --- | --- | --- |
| visa\_sponsored[] | boolean/string | true , false | Whether jobs sponsor visas or not. |

You can pass both

true

and

false

if you want to include all jobs with explicit visa metadata.

### 5.8 Industries

| Parameter | Type | Allowed Values (examples) | Description |
| --- | --- | --- | --- |
| industries[] | string (repeatable) | See list below | Filters by industry. |

Allowed values (exact strings):

administrative/support services

arts and culture

biotechnology

construction

consumer services

ecommerce

education

entertainment

farming/ranching/forestry

financial services

food and beverage

government

holding companies

hospitals/health care

hospitality

information services

insurance

legal

manufacturing

media

military and defense

nonprofit

oil/gas/mining

professional services

real estate

religious

retail

scientific/technical services

software/it services

sports/recreation

telecommunications

transportation/logistics/supply chain/storage

utilities

wholesale

### 5.9 Funding Stage

| Parameter | Type | Allowed Values | Description |
| --- | --- | --- | --- |
| funding\_stage[] | string (repeatable) | pre\_seed , seed , series\_a , series\_b , series\_c , series\_d , series\_e+ , acquired , public , private\_equity , bootstrapped , nonprofit | Filters by funding. |

### 5.10 Salary Range

| Parameter | Type | Example | Description |
| --- | --- | --- | --- |
| salary\_min | number | 0 | Minimum salary threshold. |
| salary\_max | number | 500000 | Maximum salary threshold. |

Values are numeric but sent as strings in form-encoded body.

### 5.11 Experience Range

| Parameter | Type | Example | Description |
| --- | --- | --- | --- |
| experience\_min | number | 0 | Minimum years of experience. |
| experience\_max | number | 20 | Maximum years of experience. |

### 5.12 Search Metadata

| Parameter | Type | Description |
| --- | --- | --- |
| fetch\_unique\_company\_results | boolean/string | If "true" , return a single best job per company. |

6. Response Format
------------------

The endpoint returns JSON with a

jobs

array and possibly other metadata.

{
"jobs": [
{
"id": 97373006,
"company": "The Walt Disney Company",
"company\_id": 5150,
"title": "Sr Software Engineer",
"url": "https://www.disneycareers.com/en/job/new-york/sr-software-engineer/391/87797326864",
"locations": ["New York, New York", "San Francisco, California"],
"lastUpdated": "13h",
"lastUpdatedTimestamp": "2025-12-01T12:00:00Z",
"premium": true,
"salary": "",
"saved": false,
"connections": {
/\* network data (shape may vary) \*/
}
}
]
}

​

If

jobs

is missing or null, treat it as an empty array.

### 6.1 Job Object Fields

| Field | Type | Description |
| --- | --- | --- |
| id | number | Internal job ID. |
| company | string | Company name. |
| company\_id | number | Internal company ID. |
| title | string | Job title. |
| url | string | URL of the job posting. |
| locations | string[] | One or more job locations. |
| lastUpdated | string | Human-readable time since last update (e.g. "13h" ). |
| lastUpdatedTimestamp | string (ISO 8601) | Exact UTC timestamp of last update. |
| salary | string | Salary text; may be empty if not present. |
| saved | boolean | Whether the job is saved by the current user. |
| premium | boolean | Whether the job/company is premium-tier. |
| connections | object | Direct or second-degree connection information. |

### 6.2 Error Responses

Exact shape may vary, but a typical error looks like:

{
"error": "Invalid API token"
}

​

If you want, I can now add a short “How to import into Postman” section and pre-built cURL snippets for a few common personas (Customer Success, AE, SWE, etc.) that you can reuse in docs or onboarding.
# Failure Report

- Total: **852**
- Success: **764 (89.7%)**
- Failure: **88**

## By category

| Category | Count |
|----------|-------|
| http_404 | 27 |
| dns_error | 21 |
| captcha_or_login_wall | 20 |
| ssl_error | 6 |
| insufficient_content | 5 |
| http_5xx | 4 |
| connection_refused | 4 |
| redirect_loop | 1 |

## Top failure domains (top 25)

| Domain | Count |
|--------|-------|
| angel.co | 11 |
| jobs.lever.co | 7 |
| boards.greenhouse.io | 3 |
| mobilejazz.com | 2 |
| www.abiturma.de | 1 |
| careers.aerolab.co | 1 |
| andela.com | 1 |
| corp.betable.com | 1 |
| codeship.com | 1 |
| weloveremotejobs.com | 1 |
| www.devspotlight.com | 1 |
| www.ecosmic.space | 1 |
| www.emsisoft.com | 1 |
| grnh.se | 1 |
| www.epicgames.com | 1 |
| www.episource.com | 1 |
| careers.findify.io | 1 |
| fire-engine-red.com | 1 |
| www.fleetio.com | 1 |
| jobs.gitbook.com | 1 |
| gitprime.com | 1 |
| goldfireagency.com | 1 |
| build.gr.ps | 1 |
| www.headforwards.com | 1 |
| www.homeflicwegrow.com | 1 |

## Sample failures (per category, up to 8 each)

### http_404 (27)

- **Alan** -> https://jobs.lever.co/alan  
  `http_404 page not found`
- **Andela** -> https://andela.com/join-andela/  
  `http_404 page not found`
- **Circonus** -> https://jobs.lever.co/circonus  
  `http_404 page not found`
- **Dev Spotlight** -> https://www.devspotlight.com/work-for-us/  
  `http_404 page not found`
- **Ecosmic** -> https://www.ecosmic.space/data-engineer  
  `http_404 page not found`
- **Envoy** -> https://grnh.se/83f7cd0f2us  
  `http_404 page not found`
- **Episource** -> https://www.episource.com/careers/  
  `http_404 page not found`
- **Fire Engine Red** -> https://fire-engine-red.com/general-contact-form/  
  `http_404 page not found`

### dns_error (21)

- **Bugfender** -> https://mobilejazz.com/jobs  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://mobilejazz.com/jobs`
- **Findify** -> https://careers.findify.io  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://careers.findify.io/`
- **GitPrime** -> https://gitprime.com/jobs/  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://gitprime.com/jobs/`
- **Grou.ps** -> https://build.gr.ps/careers/  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://build.gr.ps/careers/`
- **Homeflic wegrow** -> https://www.homeflicwegrow.com/hiring/  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.homeflicwegrow.com/hiring/`
- **Impira** -> https://www.impira.com/careers  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.impira.com/careers`
- **Jolly Good Code** -> https://jollygoodcode.com  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://jollygoodcode.com/`
- **kea** -> https://careers.kea.ai  
  `timeout navigating to careers page: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://careers.kea.ai/`

### captcha_or_login_wall (20)

- **42 Technologies** -> https://angel.co/company/42  
  `http_403 forbidden`
- **abiturma GmbH** -> https://www.abiturma.de/jobs  
  `http_403 forbidden`
- **Adaface** -> https://angel.co/company/adaface/jobs  
  `http_403 forbidden`
- **Emsisoft** -> https://www.emsisoft.com/en/company/jobs/  
  `http_403 forbidden`
- **Epic Games** -> https://www.epicgames.com/site/en-US/careers  
  `http_403 forbidden`
- **fleetio** -> https://www.fleetio.com/careers  
  `http_403 forbidden`
- **I-Stem** -> https://wellfound.com/company/i-stem/jobs  
  `http_403 forbidden`
- **IOpipe** -> https://angel.co/iopipe  
  `http_403 forbidden`

### ssl_error (6)

- **Cyber Whale** -> https://weloveremotejobs.com/employer/cyber-whale/  
  `timeout navigating to careers page: Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://weloveremotejobs.com/employer/cyber-whale/`
- **MetaLab** -> https://www.metalab.co/careers  
  `timeout navigating to careers page: Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://www.metalab.co/careers`
- **NEXT** -> https://www.nexttrucking.com/careers/  
  `timeout navigating to careers page: Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://www.nexttrucking.com/careers/`
- **Paytm Labs** -> https://paytmlabs.com/#careers  
  `timeout navigating to careers page: Page.goto: net::ERR_SSL_VERSION_OR_CIPHER_MISMATCH at https://paytmlabs.com/#careers`
- **Research Square** -> https://www.researchsquare.com/company/careers  
  `timeout navigating to careers page: Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://www.researchsquare.com/company/careers`
- **Travis** -> https://www.travistravis.co/career  
  `timeout navigating to careers page: Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://www.travistravis.co/career`

### insufficient_content (5)

- **Betable** -> https://corp.betable.com/careers  
  `insufficient_content`
- **Headforwards** -> https://www.headforwards.com/careers/  
  `insufficient_content`
- **Konkurenta** -> https://konkurenta.com/jobs  
  `insufficient_content`
- **Progress Engine** -> https://progress-engine.com/  
  `insufficient_content`
- **ScrapingBee** -> https://scrapingbee.com  
  `insufficient_content`

### http_5xx (4)

- **Aerolab** -> http://careers.aerolab.co/  
  `http_525 server error`
- **Codeship** -> https://codeship.com/jobs  
  `http_502 server error`
- **Gitbook** -> https://jobs.gitbook.com/  
  `http_522 server error`
- **SmugMug** -> https://jobs.smugmug.com/  
  `http_502 server error`

### connection_refused (4)

- **GoldFire Agency** -> https://goldfireagency.com  
  `timeout navigating to careers page: Page.goto: net::ERR_CONNECTION_TIMED_OUT at https://goldfireagency.com/`
- **SmartCash** -> https://smartcash.cc  
  `timeout navigating to careers page: Page.goto: net::ERR_CONNECTION_TIMED_OUT at https://smartcash.cc/`
- **TractionBoard** -> https://tractionboard.io  
  `timeout navigating to careers page: Page.goto: net::ERR_CONNECTION_TIMED_OUT at https://tractionboard.io/`
- **VMware** -> https://careers.vmware.com/main/  
  `timeout navigating to careers page: Page.goto: net::ERR_CONNECTION_TIMED_OUT at https://careers.vmware.com/main/`

### redirect_loop (1)

- **New Context** -> https://www.newcontext.com/careers/  
  `timeout navigating to careers page: Page.goto: net::ERR_TOO_MANY_REDIRECTS at https://www.newcontext.com/careers/`

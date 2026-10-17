# Initial security feed inventory

Read-only HTTP/XML checks performed on 2026-10-17 from the agent host. These are observations, not live Habiki ingestion results or guarantees of ongoing publication. 'Valid' means a parseable RSS/Atom document with entries. Entry dates below refer to the first listed entry observed, not a guarantee that all entries were sorted by publication date. Automated request failures are not proof that a publisher has ceased operating.

50 supplied entries collapse to 47 catalogue records: Architect Security was supplied twice verbatim, and Microsoft and Google each had two URLs for the same subscription. Proposed initial policy: 39 enabled records, eight disabled records. Enabled stale feeds carry warnings. ZDNet is explicitly relabelled as general news rather than misrepresented as security-only.

## Working supplied endpoints (26 records)

| Stable ID | Original and proposed URL | Notes |
|---|---|---|
| black-swan-security | https://blog.blackswansecurity.com/feed/ | Valid; first entry 2022-01-09; stale warning |
| scott-helme | https://scotthelme.co.uk/rss/ | Valid |
| troy-hunt | https://www.troyhunt.com/rss/ | Valid |
| nist-news | https://www.nist.gov/news-events/news/rss.xml | Valid; general NIST news |
| first-releases | https://www.first.org/newsroom/releases/rss.xml | Valid |
| schneier | https://www.schneier.com/feed/atom/ | Valid Atom |
| cyber-security-hub | https://www.cshub.com/rss/articles | Valid |
| sans-isc | https://isc.sans.edu/rssfeed_full.xml | Valid |
| check-point | https://blog.checkpoint.com/feed/ | Valid |
| ncsc-reports | https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml | Valid; first entry 2025-05-07; stale warning |
| architect-security | https://architectsecurity.org/feed/ | Valid; supplied twice; first entry 2026-03-27 |
| last-watchdog | https://www.lastwatchdog.com/feed/ | Valid |
| graham-cluley | https://grahamcluley.com/feed/ | Valid |
| tao-security | https://taosecurity.blogspot.com/feeds/posts/default | Valid Atom |
| unsupervised-learning | https://rss.beehiiv.com/feeds/gQxaV1KHkQ.xml | Valid; title identifies Unsupervised Learning |
| cio | https://www.cio.com/feed/ | Valid; General Technology category |
| cso-online | https://www.csoonline.com/feed/ | Valid |
| pcmag-uk | https://uk.pcmag.com/feed.xml | Valid; General Technology category |
| hacker-news | https://feeds.feedburner.com/TheHackersNews | Valid |
| ars-technica | https://feeds.arstechnica.com/arstechnica/index | Valid; all content, General Technology category |
| help-net-security | https://www.helpnetsecurity.com/feed/ | Valid |
| computerworld | https://www.computerworld.com/feed/ | Valid; General Technology category |
| it-security-guru | https://www.itsecurityguru.org/feed/ | Valid |
| security-boulevard | https://securityboulevard.com/feed/ | Initially 403; valid using Miniflux/2.3.3 user-agent |
| gbhackers | https://gbhackers.com/feed/ | Initially 403; valid using Miniflux/2.3.3 user-agent |
| heimdal-security | https://feeds.feedburner.com/HeimdalSecurityBlog | Valid |

## Redirects and verified replacements (13 records)

Keep original URLs as explicit matching aliases; categories below are policy guidance, not a required exhaustive taxonomy.

| Stable ID | Original URL(s) | Proposed catalogue URL | Observation |
|---|---|---|---|
| krebs | http://krebsonsecurity.com/feed/ | https://krebsonsecurity.com/feed/ | Valid HTTPS destination |
| portswigger | http://blog.portswigger.net/feeds/posts/default | https://portswigger.net/blog/rss | Valid redirect destination |
| register-security | https://www.theregister.com/security/headlines.atom | https://www.theregister.com/security/headlines.atom | Valid via API redirect; retain readable publisher URL |
| dark-reading | https://www.darkreading.com/rss_simple.asp | https://www.darkreading.com/rss.xml | Original redirects to HTML; replacement parses with 50 entries |
| sc-media | https://www.scmagazine.com/home/security-news/feed/ | https://www.scworld.com/rss | Original redirects to 404; replacement works with Miniflux/2.3.3 and redirects to https://www.scworld.com/feed/topic/latest |
| microsoft-security | https://www.microsoft.com/security/blog/feed/ ; https://www.microsoft.com/en-us/security/blog/feed/ | https://www.microsoft.com/en-us/security/blog/feed/ | Two supplied URLs, one subscription |
| security-affairs | https://securityaffairs.co/wordpress/feed | https://securityaffairs.com/feed | Valid redirect destination |
| smashing-security | https://feeds.fireside.fm/smashingsecurity/rss | https://www.smashingsecurity.com/rss | Original 404; publisher subscription page advertises replacement, which redirects to https://feeds.redcircle.com/c478d684-038f-4b13-8507-bc32af486a2c ; valid RSS, 490 entries, approximately 9.7 MB |
| brake-security | https://brakeingsecurity.com/rss | https://brakeingsecurity.libsyn.com/rss | Original TLS chain verification failed; replacement redirects to https://rss.libsyn.com/shows/50535/destinations/177487.xml ; valid RSS, BrakeSec Education Podcast, 474 entries, approximately 5.1 MB |
| google-security | http://googleonlinesecurity.blogspot.com/atom.xml ; https://security.googleblog.com/feeds/posts/default?alt=rss | https://feeds.feedburner.com/GoogleOnlineSecurityBlog | Both originals converge on the same HTTP FeedBurner endpoint; HTTPS destination independently parsed successfully; first entry 2026-04-23, freshness warning |
| securityweek | https://feeds.feedburner.com/securityweek | https://www.securityweek.com/feed/ | Valid redirect destination |
| europol | https://www.europol.europa.eu/rss.xml | https://www.europol.europa.eu/cms/api/rss/news | Valid RSS redirect destination |
| zdnet-news | https://www.zdnet.com/blog/security/rss.xml | https://www.zdnet.com/rss/news/ | Valid Atom but scope changed to general news; title/category MUST say so; tested /topic/security/rss.xml also redirected to general news |

## Disabled pending revalidation or replacement (8 records)

Retain each original URL and reason in the catalogue. Disabled means 'do not provision', not 'unsubscribe an existing feed'. Do not invent or auto-adopt an unverified replacement.

| Stable ID | Original and proposed retained URL | Observation |
|---|---|---|
| forbes-davey-winder | https://www.forbes.com/sites/daveywinder/feed/ | 403 with browser-like and Miniflux user-agents; blocked/unverified |
| ico-decisions | https://ico.org.uk/global/rss-feeds/decision-notices/ | HTML explicitly states the RSS feed is currently unavailable after redesign |
| ico-news | https://ico.org.uk/global/rss-feeds/news-and-blogs/ | HTML explicitly states the RSS feed is currently unavailable after redesign |
| ico-enforcement | https://ico.org.uk/global/rss-feeds/enforcement/ | HTML explicitly states the RSS feed is currently unavailable after redesign |
| sans-dfir | http://digital-forensics.sans.org/blog/feed/ | Redirects to https://www.sans.org/cybersecurity-focus-areas/digital-forensics-incident-response , an HTML landing page |
| shiftsec-left | http://shiftsectotheleft.com/feed/ | DNS resolution failed |
| greathorn | https://www.greathorn.com/feed/ | Feed and homepage returned 404 |
| threatpost | https://threatpost.com/feed/ | Timed out twice; inconclusive availability |

## Primary references

- https://www.smashingsecurity.com/subscribe/ (publisher-advertised podcast RSS)
- https://ico.org.uk/global/rss-feeds/ and the three individual ICO URLs above (explicit unavailability notices)
- https://miniflux.app/docs/api.html (native authentication, subscriptions, categories, OPML)

Before implementation acceptance, repeat checks from Habiki, verify feed creation with the pinned Miniflux parser and bounded fetch limits, and record actual ingestion outcomes. Do not disable TLS verification to make the original BrakeSec host pass. Do not claim that the live reader has already been populated.

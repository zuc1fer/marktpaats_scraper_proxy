# Marktplaats Scraper — Proxy-Enabled

Lightweight, high-performance scraper for `marktplaats.nl` (phones, listing links, full info with WhatsApp links).  
This version adds **proxy support** over the previous proxyless release.

---

## 🚀 Features
- Parallel scraping (thread pool) for speed.
- Proxy support with rotation from `proxies.txt`.
- Intelligent filtering to skip business/webshop listings.
- Extracts seller name, location, phone, price, WhatsApp link, and URL.
- Outputs: `phones.json`, `links.json`, `all_info.json`.
- Multiple keyword support with `|` or `||`.

---

## ⚙️ Installation

1. Install Python 3.8+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 📁 Files

- `scraper_v2.py` — main scraper script.
- `proxies.txt` — list of proxies (`hostname:port:username:password`).
- `requirements.txt` — dependencies.
- `README.md` — this file.

---

## 🧠 Usage

Run with proxies (default):
```bash
python scraper_v2.py --keyword "guitars"
```

Run without proxies:
```bash
python scraper_v2.py --keyword "guitars" --no-proxy
```

Common options:
```
--keyword, -k      Search term(s), use | or || to separate
--pages, -p        Number of search pages to scan
--max, -m          Max listings per keyword (default 1000)
--workers          Thread count (default 150)
--delay            Delay between requests (default 0.2)
--proxies-file     Path to proxies file (default proxies.txt)
--use-proxy        Enable proxies (default)
--no-proxy         Disable proxies
```

Example:
```bash
python scraper_v2.py -k "drums | keyboards" --proxies-file proxies.txt --workers 80 --delay 0.15
```

---

## 🧩 proxies.txt format
```
1.2.3.4:8080:user1:pass1
198.51.100.23:3128:proxyuser:proxypass
# comment lines allowed with '#'
```

---

## 📦 Output Files
- `phones.json` — normalized phone numbers.
- `links.json` — scraped listing URLs.
- `all_info.json` — detailed entries.

Each can be renamed using CLI arguments.

---

## 🔧 Tips
- Lower `--workers` or increase `--delay` if you get many timeouts.
- Check `--no-proxy` mode to debug proxy issues.
- Use good quality proxies for reliable results.

---

## 🧾 License
You can license this however you prefer (MIT recommended).

---

## 🧠 Notes
This version extends your earlier proxyless scraper with:
- Session-based proxy handling.
- Per-request rotation.
- Graceful fallback to direct connections.

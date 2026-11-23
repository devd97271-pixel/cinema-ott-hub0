import os
import re
import json
import datetime
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
OMDB_API_KEY = os.environ["OMDB_API_KEY"]
GITHUB_USER = os.environ["GITHUB_REPOSITORY_OWNER"]
REPO_NAME = os.environ["GITHUB_REPOSITORY"].split("/")[-1]
BASE_URL = f"https://{GITHUB_USER}.github.io/{REPO_NAME}"

NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
TODAY_STR = NOW.strftime("%Y-%m-%d")
YEAR_STR = NOW.strftime("%Y")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

PLATFORMS = [
    {
        "key": "netflix",
        "name": "Netflix",
        "badge": "NETFLIX",
        "color": "#E50914",
        "aliases": ["netflix"],
        "jw_slug": "netflix",
    },
    {
        "key": "prime",
        "name": "Prime Video",
        "badge": "prime video",
        "color": "#00A8E1",
        "aliases": ["amazon prime video", "prime video"],
        "jw_slug": "amazon-prime-video",
    },
    {
        "key": "jiohotstar",
        "name": "JioHotstar",
        "badge": "JioHotstar",
        "color": "#1D8CF8",
        "aliases": ["jiohotstar", "jio hotstar", "disney+ hotstar", "hotstar", "jiocinema"],
        "jw_slug": "hotstar",
    },
    {
        "key": "mxplayer",
        "name": "Amazon MX Player",
        "badge": "MX PLAYER",
        "color": "#2196F3",
        "aliases": ["amazon mx player", "mx player", "amazon minitv"],
        "jw_slug": "mx-player",
    },
    {
        "key": "sonyliv",
        "name": "SonyLIV",
        "badge": "SonyLIV",
        "color": "#F5A623",
        "aliases": ["sonyliv", "sony liv"],
        "jw_slug": "sony-liv",
    },
    {
        "key": "zee5",
        "name": "ZEE5",
        "badge": "ZEE5",
        "color": "#9B51E0",
        "aliases": ["zee5"],
        "jw_slug": "zee5",
    },
    {
        "key": "appletv",
        "name": "Apple TV+",
        "badge": " tv+",
        "color": "#FFFFFF",
        "aliases": ["apple tv+", "apple tv plus", "apple tv"],
        "jw_slug": "apple-tv-plus",
    },
    {
        "key": "hoichoi",
        "name": "Hoichoi",
        "badge": "hoichoi",
        "color": "#FF2E63",
        "aliases": ["hoichoi"],
        "jw_slug": "hoichoi",
    },
]

GENRE_MAP = {
    28: "ACTION", 12: "ADVENTURE", 16: "ANIMATION", 35: "COMEDY", 80: "CRIME",
    99: "DOCUMENTARY", 18: "DRAMA", 10751: "FAMILY", 14: "FANTASY", 36: "HISTORY",
    27: "HORROR", 10402: "MUSIC", 9648: "MYSTERY", 10749: "ROMANCE", 878: "SCI-FI",
    53: "THRILLER", 10752: "WAR", 37: "WESTERN", 10759: "ACTION", 10765: "SCI-FI",
}

os.makedirs("docs/images", exist_ok=True)
os.makedirs("docs/catalog/movie", exist_ok=True)
os.makedirs("docs/catalog/series", exist_ok=True)

OMDB_CACHE = {}
TMDB_EXTRA_CACHE = {}


def get_font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fetch_json(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def get_omdb_info(imdb_id):
    if not imdb_id:
        return None, None
    if imdb_id in OMDB_CACHE:
        return OMDB_CACHE[imdb_id]
    data = fetch_json(f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}", timeout=10)
    rating = data.get("imdbRating")
    rated = data.get("Rated")
    rating = rating if rating and rating not in ("N/A", "") else None
    rated = rated if rated and rated not in ("N/A", "") else None
    OMDB_CACHE[imdb_id] = (rating, rated)
    return rating, rated


def get_tmdb_details(media_type, tmdb_id):
    key = f"{media_type}:{tmdb_id}"
    if key in TMDB_EXTRA_CACHE:
        return TMDB_EXTRA_CACHE[key]

    endpoint = "movie" if media_type == "movie" else "tv"
    url = (
        f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}"
        f"?api_key={TMDB_API_KEY}"
        f"&append_to_response=external_ids,images,release_dates,content_ratings"
        f"&include_image_language=en,hi,bn,ta,te,ml,kn,null"
    )
    data = fetch_json(url, timeout=15)
    imdb_id = data.get("external_ids", {}).get("imdb_id")

    in_cert = None
    if media_type == "movie":
        for entry in data.get("release_dates", {}).get("results", []):
            if entry.get("iso_3166_1") == "IN":
                for rel in entry.get("release_dates", []):
                    cert = (rel.get("certification") or "").strip()
                    if cert:
                        in_cert = cert
                        break
            if in_cert:
                break
    else:
        for cr in data.get("content_ratings", {}).get("results", []):
            if cr.get("iso_3166_1") == "IN" and (cr.get("rating") or "").strip():
                in_cert = cr["rating"].strip()
                break

    logos = data.get("images", {}).get("logos", [])
    logo_url = f"https://image.tmdb.org/t/p/w500{logos[0]['file_path']}" if logos else None

    res = (imdb_id, in_cert, logo_url)
    TMDB_EXTRA_CACHE[key] = res
    return res


def get_provider_map():
    mapping = {p["key"]: set() for p in PLATFORMS}
    for mtype in ["movie", "tv"]:
        data = fetch_json(f"https://api.themoviedb.org/3/watch/providers/{mtype}?api_key={TMDB_API_KEY}&watch_region=IN")
        for item in data.get("results", []):
            pname = (item.get("provider_name") or "").lower().strip()
            pid = item.get("provider_id")
            if not pid:
                continue
            for p in PLATFORMS:
                if any(alias == pname or alias in pname for alias in p["aliases"]):
                    if p["key"] == "prime" and "channel" in pname:
                        continue
                    mapping[p["key"]].add(str(pid))
    return {k: "|".join(v) for k, v in mapping.items() if v}


def extract_page_titles(urls, limit=12):
    junk = {
        "netflix", "prime video", "amazon prime video", "jiohotstar", "hotstar",
        "mx player", "amazon mx player", "sonyliv", "zee5", "apple tv+", "hoichoi",
        "justwatch", "flixpatrol", "tudum", "bookmyshow", "kolkata", "movies",
        "tv shows", "series", "top 10", "new", "upcoming", "now showing", "india",
        "sign in", "log in", "home", "explore", "privacy", "terms"
    }
    for url in urls:
        titles = []
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and len(r.text) > 500:
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup.select("a, h1, h2, h3, h4, span, div"):
                    txt = " ".join(tag.get_text(" ", strip=True).split())
                    clean = re.sub(r"^\d+[\).\s-]+", "", txt).strip()
                    low = clean.lower()
                    if 2 <= len(clean) <= 60 and low not in junk and not low.startswith("http"):
                        if clean not in titles:
                            titles.append(clean)
                    if len(titles) >= limit:
                        break
        except Exception:
            pass
        if titles:
            return titles
    return []


def search_tmdb_by_titles(titles, media_type, limit=12):
    endpoint = "movie" if media_type == "movie" else "tv"
    out = []
    seen = set()
    for t in titles:
        q = requests.utils.quote(t)
        data = fetch_json(f"https://api.themoviedb.org/3/search/{endpoint}?api_key={TMDB_API_KEY}&query={q}&region=IN")
        results = data.get("results", [])
        if results:
            item = results[0]
            if item["id"] not in seen:
                seen.add(item["id"])
                out.append(item)
        if len(out) >= limit:
            break
    return out


def get_kolkata_cinema_movies(mode="now", limit=15):
    bms_urls = [
        "https://in.bookmyshow.com/explore/movies-kolkata",
        "https://in.bookmyshow.com/kolkata/movies",
    ]
    bms_titles = extract_page_titles(bms_urls, limit=limit)
    bms_items = search_tmdb_by_titles(bms_titles, "movie", limit=limit) if bms_titles else []

    if mode == "now":
        tmdb_url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}&region=IN&with_release_type=2|3"
            f"&primary_release_date.lte={TODAY_STR}&sort_by=popularity.desc&page=1"
        )
    else:
        tmdb_url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}&region=IN&with_release_type=2|3"
            f"&primary_release_date.gte={TODAY_STR}&sort_by=popularity.desc&page=1"
        )

    tmdb_items = fetch_json(tmdb_url).get("results", [])
    merged = []
    seen = set()
    for item in bms_items + tmdb_items:
        if item["id"] not in seen:
            seen.add(item["id"])
            merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def get_new_release_items(platform, media_type, provider_ids, limit=12):
    slug = platform["jw_slug"]
    jw_urls = [
        f"https://www.justwatch.com/in/provider/{slug}/new",
        f"https://www.justwatch.com/in/provider/{slug}",
    ]
    jw_titles = extract_page_titles(jw_urls, limit=limit)
    items = search_tmdb_by_titles(jw_titles, media_type, limit=limit) if jw_titles else []

    if not items and provider_ids:
        endpoint = "movie" if media_type == "movie" else "tv"
        date_param = "primary_release_date.lte" if media_type == "movie" else "first_air_date.lte"
        sort_param = "primary_release_date.desc" if media_type == "movie" else "first_air_date.desc"
        url = (
            f"https://api.themoviedb.org/3/discover/{endpoint}"
            f"?api_key={TMDB_API_KEY}&watch_region=IN&with_watch_providers={provider_ids}"
            f"&{date_param}={TODAY_STR}&sort_by={sort_param}&page=1"
        )
        items = fetch_json(url).get("results", [])[:limit]
    return items[:limit]


def get_top10_items(platform, media_type, provider_ids, limit=10):
    pkey = platform["key"]
    slug = platform["jw_slug"]
    titles = []

    if pkey == "netflix":
        titles = extract_page_titles([
            "https://www.netflix.com/tudum/top10/india",
            "https://www.netflix.com/tudum/top10",
        ], limit=limit)
    else:
        titles = extract_page_titles([
            "https://flixpatrol.com/top10/streaming/india/",
            "https://flixpatrol.com/top10/",
        ], limit=limit)

    if not titles:
        titles = extract_page_titles([
            f"https://www.justwatch.com/in/provider/{slug}",
        ], limit=limit)

    items = search_tmdb_by_titles(titles, media_type, limit=limit) if titles else []

    if not items and provider_ids:
        endpoint = "movie" if media_type == "movie" else "tv"
        url = (
            f"https://api.themoviedb.org/3/discover/{endpoint}"
            f"?api_key={TMDB_API_KEY}&watch_region=IN&with_watch_providers={provider_ids}"
            f"&sort_by=popularity.desc&page=1"
        )
        items = fetch_json(url).get("results", [])[:limit]

    return items[:limit]


def format_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except Exception:
        return date_str[:10]
        def render_poster(
    out_path,
    backdrop_url=None,
    logo_url=None,
    glass_rank=None,
    genre_label=None,
    date_label=None,
    age_rating=None,
    imdb_rating=None,
    platform_badge=None,
    platform_color="#FFFFFF",
):
    W, H = 960, 540

    if backdrop_url:
        try:
            resp = requests.get(backdrop_url, headers=HEADERS, timeout=15)
            bg = Image.open(BytesIO(resp.content)).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
        except Exception:
            bg = Image.new("RGBA", (W, H), (18, 20, 26, 255))
    else:
        bg = Image.new("RGBA", (W, H), (18, 20, 26, 255))

    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for x in range(W):
        if x < 410:
            alpha = int(225 - (x / 410) * 65)
        elif x < 700:
            alpha = int(160 - ((x - 410) / 290) * 160)
        else:
            alpha = 0
        gdraw.line([(x, 0), (x, H)], fill=(10, 12, 16, alpha))
    bg = Image.alpha_composite(bg, grad)

    if logo_url:
        try:
            lresp = requests.get(logo_url, headers=HEADERS, timeout=10)
            logo = Image.open(BytesIO(lresp.content)).convert("RGBA")
            logo.thumbnail((320, 130), Image.Resampling.LANCZOS)
            bg.paste(logo, (W - logo.width - 34, H - logo.height - 30), logo)
        except Exception:
            pass

    if glass_rank is not None:
        num_str = str(glass_rank)
        num_font = get_font(220 if len(num_str) == 1 else 184, bold=True)
        num_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ndraw = ImageDraw.Draw(num_layer)
        nx, ny = 42, 8
        ndraw.text((nx + 6, ny + 8), num_str, font=num_font, fill=(0, 0, 0, 140))
        ndraw.text(
            (nx, ny),
            num_str,
            font=num_font,
            fill=(255, 255, 255, 82),
            stroke_width=3,
            stroke_fill=(255, 255, 255, 155),
        )
        bg = Image.alpha_composite(bg, num_layer)
        cur_y = 278
    else:
        cur_y = 140

    draw = ImageDraw.Draw(bg)
    x0 = 44
    t_font = get_font(23, bold=True)
    b_font = get_font(25, bold=True)

    if genre_label and glass_rank is not None:
        draw.text((x0, cur_y), genre_label.upper(), font=t_font, fill=(235, 238, 245, 255))
        cur_y += 33

    if date_label:
        draw.text((x0, cur_y), date_label, font=t_font, fill=(225, 230, 240, 255))
        cur_y += 33

    if age_rating:
        draw.text((x0, cur_y), f"Rated {age_rating}", font=t_font, fill=(215, 220, 230, 255))
        cur_y += 33

    if imdb_rating:
        draw.text((x0, cur_y), "★", font=t_font, fill=(245, 197, 24, 255))
        draw.text((x0 + 28, cur_y), str(imdb_rating), font=t_font, fill=(255, 255, 255, 255))
        cur_y += 40

    if platform_badge:
        draw.text((x0, cur_y), platform_badge, font=b_font, fill=platform_color)

    bg.convert("RGB").save(out_path, "JPEG", quality=88, optimize=True)


def make_meta(item, media_type, stremio_type, img_name, glass_rank=None, platform=None):
    tmdb_id = item["id"]
    title = item.get("title") or item.get("name") or "Unknown"
    raw_date = item.get("release_date") or item.get("first_air_date") or ""
    date_str = format_date(raw_date)
    g_ids = item.get("genre_ids", [])
    genre_str = GENRE_MAP.get(g_ids[0], "DRAMA") if g_ids else None

    b_path = item.get("backdrop_path") or item.get("poster_path")
    backdrop_url = f"https://image.tmdb.org/t/p/w1280{b_path}" if b_path else None

    imdb_id, in_cert, logo_url = get_tmdb_details(media_type, tmdb_id)
    imdb_rating, omdb_rated = get_omdb_info(imdb_id)

    final_rating = imdb_rating or (f"{item['vote_average']:.1f}" if item.get("vote_average") else None)
    final_age = in_cert or omdb_rated

    out_path = f"docs/images/{img_name}"
    render_poster(
        out_path=out_path,
        backdrop_url=backdrop_url,
        logo_url=logo_url,
        glass_rank=glass_rank,
        genre_label=genre_str,
        date_label=date_str,
        age_rating=final_age,
        imdb_rating=final_rating,
        platform_badge=platform["badge"] if platform else None,
        platform_color=platform["color"] if platform else "#FFFFFF",
    )

    info_parts = []
    if date_str:
        info_parts.append(date_str)
    if final_age:
        info_parts.append(final_age)
    if final_rating:
        info_parts.append(f"IMDb {final_rating}")
    if platform:
        info_parts.append(platform["name"])

    return {
        "id": imdb_id if imdb_id else f"tmdb:{tmdb_id}",
        "type": stremio_type,
        "name": title,
        "poster": f"{BASE_URL}/images/{img_name}",
        "posterShape": "landscape",
        "releaseInfo": date_str or YEAR_STR,
        "imdbRating": final_rating,
        "description": " • ".join(info_parts) if info_parts else item.get("overview", ""),
    }


def save_catalog(stremio_type, cat_id, cat_name, metas, manifest_catalogs):
    if not metas:
        return
    with open(f"docs/catalog/{stremio_type}/{cat_id}.json", "w", encoding="utf-8") as f:
        json.dump({"metas": metas}, f, ensure_ascii=False, indent=2)
    manifest_catalogs.append({
        "type": stremio_type,
        "id": cat_id,
        "name": cat_name,
    })
    print(f"Built: {cat_name} ({len(metas)})")


def main():
    provider_map = get_provider_map()
    manifest_catalogs = []

    now_items = get_kolkata_cinema_movies(mode="now", limit=15)
    now_metas = [
        make_meta(it, "movie", "movie", f"in_cinema_{i}.jpg", glass_rank=None, platform=None)
        for i, it in enumerate(now_items, start=1)
    ]
    save_catalog("movie", "in_cinema", "In Cinema", now_metas, manifest_catalogs)

    up_items = get_kolkata_cinema_movies(mode="upcoming", limit=15)
    up_metas = [
        make_meta(it, "movie", "movie", f"upcoming_cinema_{i}.jpg", glass_rank=None, platform=None)
        for i, it in enumerate(up_items, start=1)
    ]
    save_catalog("movie", "upcoming_in_cinema", "Upcoming in Cinema", up_metas, manifest_catalogs)

    for plat in PLATFORMS:
        pkey = plat["key"]
        pname = plat["name"]
        pids = provider_map.get(pkey)

        new_m_items = get_new_release_items(plat, "movie", pids, limit=12)
        new_m_metas = [
            make_meta(it, "movie", "movie", f"{pkey}_new_m_{i}.jpg", glass_rank=None, platform=plat)
            for i, it in enumerate(new_m_items, start=1)
        ]
        save_catalog("movie", f"{pkey}_new_movie", f"New release in {pname} movie", new_m_metas, manifest_catalogs)

        new_s_items = get_new_release_items(plat, "tv", pids, limit=12)
        new_s_metas = [
            make_meta(it, "tv", "series", f"{pkey}_new_s_{i}.jpg", glass_rank=None, platform=plat)
            for i, it in enumerate(new_s_items, start=1)
        ]
        save_catalog("series", f"{pkey}_new_series", f"New release in {pname} series", new_s_metas, manifest_catalogs)

        top_m_items = get_top10_items(plat, "movie", pids, limit=10)
        top_m_metas = [
            make_meta(it, "movie", "movie", f"{pkey}_top10_m_{i}.jpg", glass_rank=i, platform=plat)
            for i, it in enumerate(top_m_items, start=1)
        ]
        save_catalog("movie", f"{pkey}_top10_movies", f"Top 10 movies in {pname}", top_m_metas, manifest_catalogs)

        top_s_items = get_top10_items(plat, "tv", pids, limit=10)
        top_s_metas = [
            make_meta(it, "tv", "series", f"{pkey}_top10_s_{i}.jpg", glass_rank=i, platform=plat)
            for i, it in enumerate(top_s_items, start=1)
        ]
        save_catalog("series", f"{pkey}_top10_series", f"Top 10 series in {pname}", top_s_metas, manifest_catalogs)

    manifest = {
        "id": f"com.{GITHUB_USER.lower()}.kolkata.cinema.ott",
        "version": "3.0.0",
        "name": "Kolkata Cinema & OTT Hub",
        "description": "In Cinema, Upcoming in Cinema & OTT New Releases + Top 10",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": manifest_catalogs,
        "idPrefixes": ["tt", "tmdb:"],
    }

    with open("docs/manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("Done building all catalogs!")


if __name__ == "__main__":
    main()
            

#!/usr/bin/env python3
"""CGV Conan new-session watcher (GitHub Actions, Python stdlib only).

Read-only: checks theater/date screening info and notifies via Telegram.
No automatic booking, purchase, login, or CAPTCHA handling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://cgv.co.kr/api/v1/booking"
STATE_FILE = Path(__file__).with_name("state.json")
KST = timezone(timedelta(hours=9))
THEATERS = {"0074": "왕십리", "0191": "홍대"}
CO_CD = "A420"
DAYS_AHEAD = 30  # Future day limit; actual monitored dates are based on CGV's open-day list.
MAX_DATES_PER_THEATER = 14  # Caps requests per run.
REQUEST_GAP_SECONDS = 0.4
TELEGRAM_API = "https://api.telegram.org/bot"

# Ordinary client request headers. If CGV blocks access, do not retry aggressively.
CGV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://cgv.co.kr/cnm/movieBook/cinema",
    "Origin": "https://cgv.co.kr",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def now_kst():
    return datetime.now(KST)


def request_json(url, headers=None, payload=None):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h = dict(headers or {})
    if body is not None:
        h["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=18) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} ({urllib.parse.urlsplit(url).netloc}). "
                           "403=접근 제한, 429=요청 제한일 수 있습니다.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"연결/JSON 오류: {exc}") from exc


def cgv_get(endpoint, **params):
    params = {"coCd": CO_CD, **params}
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    response = request_json(url, CGV_HEADERS)
    if not isinstance(response, dict) or str(response.get("statusCode")) not in ("0", "0000"):
        raise RuntimeError(f"CGV 응답 오류({endpoint}): {str(response)[:200]}")
    return response.get("data")


def as_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("scnYmdList", "list", "siteInfo", "result", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
        list_values = [v for v in data.values() if isinstance(v, list)]
        if len(list_values) == 1:
            return list_values[0]
    if data is None:
        return []
    raise RuntimeError("예상과 다른 CGV 응답 형식 (사이트가 변경되었을 수 있음)")


def dates_for_theater(site_no, today=None):
    """Gets schedule day listing, including days when Conan isn't yet playing."""
    today = today or now_kst().date()
    data = as_list(cgv_get("searchSiteScnscYmdListBySite", siteNo=site_no))
    start = today.strftime("%Y%m%d")
    end = (today + timedelta(days=DAYS_AHEAD)).strftime("%Y%m%d")
    dates = set()
    for item in data:
        d = item.get("scnYmd") if isinstance(item, dict) else str(item)
        if d and re.fullmatch(r"\d{8}", str(d)) and start <= str(d) <= end:
            dates.add(str(d))
    return sorted(dates)[:MAX_DATES_PER_THEATER]


def is_conan(name):
    normalized = re.sub(r"[\s\W_]+", "", str(name or "").lower(), flags=re.UNICODE)
    return "코난" in normalized or "detectiveconan" in normalized or "caseclosed" in normalized


def session_from_row(site_no, fallback_date, row):
    if not isinstance(row, dict):
        return None
    name = row.get("movNm") or row.get("expoProdNm") or ""
    if not is_conan(name):
        return None
    ymd = str(row.get("scnYmd") or fallback_date)
    hhmm = str(row.get("scnsrtTm") or "").replace(":", "")
    if not re.fullmatch(r"\d{8}", ymd) or not re.fullmatch(r"\d{4}", hhmm):
        raise RuntimeError("코난 회차의 날짜/상영시간 응답이 변경되었습니다")
    movie_no = str(row.get("movNo") or name)
    screen_no = str(row.get("scnsNo") or row.get("scnsNm") or "unknown")
    screen_label = str(row.get("scnsNm") or row.get("movkndDsplNm") or screen_no)
    format_label = str(row.get("movkndDsplNm") or "")
    key = "|".join((site_no, movie_no, ymd, hhmm, screen_no))
    return {
        "key": key, "site": site_no, "date": ymd,
        "time": hhmm, "movie": name, "screen": screen_label, "format": format_label,
    }


def fetch_sessions():
    found = {}
    for site_no, theater_name in THEATERS.items():
        dates = dates_for_theater(site_no)
        print(f"CGV {theater_name}: 확인할 상영일 {len(dates)}개", flush=True)
        for date in dates:
            time.sleep(REQUEST_GAP_SECONDS)
            rows = as_list(cgv_get("searchMovScnInfo", siteNo=site_no,
                                   scnYmd=date, rtctlScopCd="08"))
            for row in rows:
                session = session_from_row(site_no, date, row)
                if session:
                    found[session["key"]] = session
    return found


def load_state():
    if not STATE_FILE.exists():
        return {"initialized": False, "seen": [], "last_warning_date": ""}
    saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or not isinstance(saved.get("seen", []), list):
        raise RuntimeError("state.json 형식이 올바르지 않습니다")
    return saved


def save_state(state):
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(STATE_FILE)


def telegram_send(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("GitHub Secrets에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 등록해야 합니다")
    url = f"{TELEGRAM_API}{token}/sendMessage"
    try:
        result = request_json(url, payload={
            "chat_id": chat_id, "text": message,
            "disable_web_page_preview": True,
        })
    except RuntimeError as exc:
        # Never put full URL with token in logs.
        raise RuntimeError("텔레그램 전송 실패: 토큰, 채팅 ID, 봇의 시작 여부를 확인하세요") from exc
    if not result.get("ok"):
        raise RuntimeError("텔레그램 전송 거절: " + str(result.get("description", "원인 알 수 없음")))
    return result


def book_url(site_no):
    return "https://cgv.co.kr/cnm/movieBook/cinema?" + urllib.parse.urlencode({
        "siteNo": site_no, "siteNm": THEATERS[site_no]
    })


def format_notice(site_no, sessions):
    lines = ["🎬 CGV 코난 예매 신규 회차!", f"📍 CGV {THEATERS[site_no]}", ""]
    for s in sessions:
        d = s["date"]
        day = f"{d[4:6]}/{d[6:8]}"
        t = f"{s['time'][:2]}:{s['time'][2:]}"
        desc = s["screen"]
        if s["format"] and s["format"] not in desc:
            desc += f" · {s['format']}"
        lines.append(f"🎞 {s['movie']}")
        lines.append(f"🗓 {day} {t} · {desc}")
        lines.append("")
    lines.extend(["🎟 CGV에서 직접 예매:", book_url(site_no),
                  f"⏱ 감지: {now_kst().strftime('%Y-%m-%d %H:%M')} KST"])
    return "\n".join(lines)


def cleanup_seen(seen):
    cutoff = (now_kst().date() - timedelta(days=1)).strftime("%Y%m%d")
    result = []
    for key in seen:
        parts = key.split("|")
        if len(parts) >= 5 and parts[2] >= cutoff:
            result.append(key)
    return sorted(set(result))


def run_once(fetcher=fetch_sessions, sender=telegram_send):
    state = load_state()
    try:
        sessions = fetcher()  # Any partial site failure => fail closed, don't lose baseline.
    except Exception as exc:
        print("CGV 조회 실패:", str(exc), file=sys.stderr)
        today = now_kst().date().isoformat()
        if state.get("last_warning_date") != today:
            try:
                sender("⚠️ CGV 코난 감시 조회 실패\n"
                       "왕십리·홍대 자동 감시를 확인해 주세요.\n"
                       f"원인: {str(exc)[:180]}\n"
                       "GitHub → Actions → 최근 실행 기록을 확인하세요.")
                state["last_warning_date"] = today
                save_state(state)
            except Exception as notify_exc:
                print("오류 경고 알림도 실패:", str(notify_exc), file=sys.stderr)
        raise
    today = now_kst().date().isoformat()
    if state.get("last_warning_date"):
        state["last_warning_date"] = ""  # Re-enable warnings on a future outage.
    seen = set(cleanup_seen(state.get("seen", [])))
    if not state.get("initialized"):
        seen.update(sessions)
        state.update({"initialized": True, "seen": sorted(seen),
                      "last_check_date": today})
        save_state(state)
        print(f"첫 검사 완료: 기존 코난 회차 {len(sessions)}개를 기준선으로 저장 (알림 없음)")
        return 0

    fresh = [session for key, session in sessions.items() if key not in seen]
    print(f"감지된 코난 회차 {len(sessions)}개 / 새 회차 {len(fresh)}개")
    # One notification per site per <=10 newly added sessions.
    for site_no in THEATERS:
        additions = sorted((x for x in fresh if x["site"] == site_no),
                           key=lambda x: (x["date"], x["time"], x["screen"]))
        for pos in range(0, len(additions), 10):
            batch = additions[pos:pos + 10]
            sender(format_notice(site_no, batch))
            seen.update(x["key"] for x in batch)
            state["seen"] = sorted(seen)
            state["last_check_date"] = today
            save_state(state)  # Save after each successfully sent notification.
            print(f"CGV {THEATERS[site_no]} 새 회차 알림 {len(batch)}건 발송")
    if not fresh:
        # Commit a small heartbeat approximately monthly to help prevent
        # public-repository scheduled workflows being disabled after inactivity.
        last = state.get("last_check_date", "")
        if not last or (now_kst().date() - datetime.strptime(last, "%Y-%m-%d").date()).days >= 25:
            state["last_check_date"] = today
            state["seen"] = cleanup_seen(seen)
            save_state(state)
    return len(fresh)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Send test Telegram message without CGV requests")
    args = parser.parse_args()
    if args.test:
        telegram_send("✅ CGV 코난 알림 연결 테스트 성공!\n"
                      "📍 왕십리 / 홍대\n"
                      "🎞 명탐정 코난 (모든 상영관)\n"
                      "실제 감시가 되는지는 Actions의 'check' 실행으로 별도 확인하세요.")
        print("텔레그램 테스트 메시지 전송 성공")
        return
    run_once()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("실행 실패:", str(error), file=sys.stderr)
        sys.exit(1)

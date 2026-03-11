#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
섭라 존윅 킬카운터 - 카카오톡 채팅 파서
로직: 시스템 메시지 'OOO님이 나갔습니다.' 직전에 발언한 사람이 킬 획득
      한 발언 후 여러 명이 나가면 멀티킬 적립
사용법: python parse_kakao.py 채팅파일.txt
"""

import re
import sys
import json
from datetime import datetime, timedelta, timezone

# ==============================
# 설정
# ==============================

OUTPUT_FILE = "chatdata.js"

# killer에서 제외할 닉네임 목록
EXCLUDE_KILLERS = ["오픈채팅봇"]

# ==============================

# 시스템 퇴장 메시지 패턴 (prefix 없는 순수 시스템 메시지만)
EXIT_PATTERN = re.compile(r'^(.+?)님이 나갔습니다\.$')

# 일반 메시지 패턴: [닉네임] [오전/오후 H:MM] 메시지
MSG_PATTERN = re.compile(r'^\[(.+?)\]\s+\[(오전|오후)\s+(\d{1,2}):(\d{2})\]\s+(.+)$')

# 날짜 헤더 패턴
DATE_PATTERN = re.compile(r'(\d{4})년\s+(\d{1,2})월\s+(\d{1,2})일')


def to_24h(am_pm, hour, minute):
    if am_pm == '오후' and hour != 12:
        hour += 12
    elif am_pm == '오전' and hour == 12:
        hour = 0
    return hour, minute


def parse_kakao_txt(filepath):
    """카카오톡 .txt 파일을 파싱해서 킬 목록 반환"""

    kills = []
    current_date = None
    last_msg = None  # 직전 일반 메시지

    # 인코딩 자동 감지
    lines = None
    for enc in ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                lines = f.readlines()
            print(f"✅ 파일 읽기 성공 (인코딩: {enc})")
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if lines is None:
        print("❌ 파일 인코딩을 자동 감지할 수 없습니다.")
        sys.exit(1)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # ── 날짜 헤더 ──────────────────────────────────────────
        date_match = DATE_PATTERN.search(line)
        if date_match and '---' in line:
            try:
                current_date = datetime(
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3))
                )
            except ValueError:
                pass
            continue

        # ── 일반 채팅 메시지 ────────────────────────────────────
        msg_match = MSG_PATTERN.match(line)
        if msg_match and current_date:
            nickname = msg_match.group(1).strip()
            am_pm    = msg_match.group(2)
            hour     = int(msg_match.group(3))
            minute   = int(msg_match.group(4))
            message  = msg_match.group(5).strip()

            hour, minute = to_24h(am_pm, hour, minute)

            # 제외 닉네임은 last_msg 갱신 안 함
            if nickname not in EXCLUDE_KILLERS:
                last_msg = {
                    "date":    current_date.strftime("%Y-%m-%d"),
                    "time":    f"{hour:02d}:{minute:02d}",
                    "killer":  nickname,
                    "message": message,
                }
            # 채팅 메시지이므로 퇴장 체크 없이 반드시 continue
            continue

        # ── 시스템 퇴장 메시지 ─────────────────────────────────
        # [닉네임][시간] prefix가 없는 순수 시스템 메시지만 여기에 도달
        exit_match = EXIT_PATTERN.match(line)
        if exit_match and last_msg:
            pass  # 아래에서 처리
        elif not exit_match and last_msg:
            # 날짜 헤더도, 채팅 메시지도, 퇴장 메시지도 아닌 줄
            # → 직전 메시지의 줄바꿈 연속 내용
            last_msg["message"] += "\n" + line

        if exit_match and last_msg:
            exited_name = exit_match.group(1).strip()
            kills.append({
                "date":      last_msg["date"],
                "time":      last_msg["time"],
                "killer":    last_msg["killer"],
                "message":   last_msg["message"],
                "exited":    exited_name,
                "killCount": 1,
            })
            # last_msg를 초기화하지 않음 → 연속 퇴장 시 같은 killer에게 멀티킬 적립

    return kills


def generate_stats(kills):
    stats = {}
    for k in kills:
        name = k["killer"]
        stats[name] = stats.get(name, 0) + 1
    return stats


def main():
    if len(sys.argv) < 2:
        print("사용법: python parse_kakao.py 채팅파일.txt")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"\n📂 파일 파싱 중: {filepath}")

    kills = parse_kakao_txt(filepath)

    if not kills:
        print("⚠️  킬 데이터를 찾을 수 없습니다.")
        sys.exit(1)

    print(f"🎯 총 킬 감지: {len(kills)}개")

    stats = generate_stats(kills)
    sorted_killers = sorted(stats.items(), key=lambda x: x[1], reverse=True)

    print("\n📊 상위 5명:")
    for i, (name, count) in enumerate(sorted_killers[:5], 1):
        print(f"   {i}. {name}: {count}킬")

    dates = [k["date"] for k in kills]
    print(f"\n📅 데이터 기간: {min(dates)} ~ {max(dates)}")

    kst = timezone(timedelta(hours=9))
    updated_at = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M")
    output = f"""// 섭라 존윅 킬 카운터 - 자동 생성된 데이터
// 생성: {updated_at}
// 로직: 누군가 나갔을 때 직전에 메시지를 보낸 사람이 킬 획득

const CHAT_DATA = {{
  updatedAt: "{updated_at}",
  kills: {json.dumps(kills, ensure_ascii=False, indent=2)}
}};
"""

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\n✅ {OUTPUT_FILE} 생성 완료!")


if __name__ == "__main__":
    main()

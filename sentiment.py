"""Low-cost, local sentiment / issue categorization for lock-screen discussions.

English VADER is combined with domain-specific phrases. No external AI or API key.
The labels are *estimates*, not ground-truth. News is not sentiment scored.
"""
import re
from functools import lru_cache

VERSION = "v4-vader-rules"
TOPICS = [
    ("勝手に有効化", [r"\bre[- ]?enable[ds]?\b", r"\bturned on (again|automatically)\b",
                    r"\bwithout (my )?(permission|consent)\b", r"\bforce[ds]?\b",
                    r"\bpre[- ]?install", r"\bkeeps (coming|turning) back\b",
                    r"\b勝手に\b", r"\b強制\b"]),
    ("停止・削除", [r"\b(can'?t|cannot|unable to|won'?t|doesn'?t let me)\s+(disable|uninstall|remove|turn off)\b",
                 r"\bhow (can i|do i|to) (disable|uninstall|remove|turn off|get rid)\b",
                 r"\bnot (possible|able) to (disable|remove)\b", r"\bdisable\b",
                 r"\buninstall\b", r"\b削除できない\b", r"\b消せない\b"]),
    ("広告への不満", [r"\b(adware|spam|intrusive|annoying ads?|pop[- ]?ups?|unwanted ads?|ads everywhere)\b",
                  r"\btoo many ads?\b", r"\b広告が?うざ", r"\b邪魔な広告\b"]),
    ("性能・電池", [r"\bbattery (drain|life)\b", r"\bdrain(s|ing)? battery\b",
                  r"\b(lag|laggy|slowdown|sluggish|overheat|performance)\b",
                  r"\b電池\b", r"\b重くなる\b"]),
    ("プライバシー", [r"\b(privacy|tracking|data collection|spyware|surveillance)\b",
                   r"\b個人情報\b", r"\b追跡\b"]),
    ("コンテンツ", [r"\b(recommendations?|news feed|wallpapers?|content|shopping|discover)\b",
                 r"\bニュース\b", r"\b壁紙\b", r"\b情報\b"])
]
NEGATIVE = [
    r"\b(can'?t|cannot|unable to|won'?t)\s+(disable|uninstall|remove|turn off)\b",
    r"\bkeeps (coming|turning) back\b", r"\b(re[- ]?enable[ds]?|unwanted|intrusive|adware|spam|annoying|irritating|terrible|awful|hate|worst|horrible|invasive|scam|trash|garbage|ridiculous|forced)\b",
    r"\b(no|without my) (permission|consent)\b", r"\bwhy (is|does) (this|it|glance).{0,35}(back|installed|exist)\b",
    r"\bdrain(s|ing)? battery\b", r"\b(ruin|ruins|ruined) (my |the )?(phone|experience)\b",
    r"\b勝手に\b", r"\bうざい\b", r"\b迷惑\b", r"\b最悪\b", r"\b嫌い\b", r"\b邪魔\b"
]
POSITIVE = [
    r"\b(love|great|amazing|awesome|excellent|useful|helpful|convenient|enjoy|fantastic|beautiful|nice feature|works well|actually like)\b",
    r"\b(so handy|really good|pretty cool|looks good)\b",
    r"\b便利\b", r"\b好き\b", r"\b最高\b", r"\b役に立つ\b"
]
_NEG = [re.compile(p, re.I) for p in NEGATIVE]
_POS = [re.compile(p, re.I) for p in POSITIVE]
_TOPIC = [(name,[re.compile(p,re.I) for p in patterns]) for name,patterns in TOPICS]

@lru_cache(maxsize=1)
def vader():
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except ImportError:
        return None

def classify(text, brand=None):
    """Return a transparent, conservative local estimate and issue category."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()[:3000]
    if not s or s.lower() in ("[deleted]", "[removed]"):
        return {"sentiment": "unclear", "score": 0.0, "topic": "その他",
                "reason": "判断に十分な文章がありません", "classifier": VERSION}
    neg = sum(bool(p.search(s)) for p in _NEG)
    pos = sum(bool(p.search(s)) for p in _POS)
    topic = next((name for name,patterns in _TOPIC if any(p.search(s) for p in patterns)), "その他")
    analyzer = vader()
    compound = analyzer.polarity_scores(s)["compound"] if analyzer else 0.0
    # Directions, troubleshooting replies and support boilerplate are not
    # evidence of the writer's own positive/negative experience.
    support = bool(re.search(r"^(hi|hello)\s+u/|\bwe\s+(truly\s+)?(empathize|understand)\b|\bplease\s+(try|check|go to)\b", s, re.I))
    instructions = bool(re.search(r"\b(which phone do you have|go to (the )?settings|in settings app|tap (on )?settings|turn it off in settings|you can disable it)\b", s, re.I))
    if support or (instructions and not neg and not pos):
        label, reason = "neutral", "操作案内やサポート返信であり、明確な本人の評価ではありません"
    elif neg and pos:
        label, reason = "unclear", "肯定・否定の両方の表現を含みます"
    elif neg:
        label, reason = "negative", "不満・問題を表す表現が見られます"
    elif pos:
        label, reason = "positive", "好意的な表現が見られます"
    elif analyzer and compound <= -0.45:
        label, reason = "negative", "否定的な表現が見られます（VADER推定）"
    elif analyzer and compound >= 0.55:
        label, reason = "positive", "好意的な表現が見られます（VADER推定）"
    elif len(re.findall(r"[a-zA-Z]+", s)) < 4 and not re.search(r"[ぁ-んァ-ヶ一-龯]{4,}", s):
        label, reason = "unclear", "感情を判断する言葉が不足しています"
    else:
        label, reason = "neutral", "明確な肯定・否定が見られません"
    if label == "positive" and brand in ("Glance", "Unity Aura"):
        # Generic praise for the phone/other app must not become praise
        # for the lock-screen product merely because it is mentioned.
        target = r"\b(?:glance|unity aura)\b"
        praise = r"\b(?:love|like|useful|helpful|convenient|good|great|nice|awesome|amazing|beautiful|enjoy|better|fantastic|recommend|prefer)\b"
        target_praise = bool(re.search(target+r".{0,70}"+praise+"|"+praise+r".{0,70}"+target, s, re.I))
        removed_then_improved = bool(re.search(
            r"\b(?:remove|removed|uninstall|deleted|disable|debloat)\w*\b.{0,80}\b(?:better|good|great|fine|improved)\b", s, re.I))
        if not target_praise or removed_then_improved:
            label, reason = "neutral", "肯定的な表現が対象サービスへの評価とは確認できません"
    return {"sentiment": label, "score": round(compound, 3), "topic": topic,
            "reason": reason, "classifier": VERSION}

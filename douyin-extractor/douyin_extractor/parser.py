"""抖音链接解析与视频数据获取模块

支持格式：
- 分享口令: "7.43 pda:/ 让你记住我 https://v.douyin.com/L5pbfdP/ 复制此链接..."
- 短网址: https://v.douyin.com/L5pbfdP/
- 标准网址: https://www.douyin.com/video/6914948781100338440
- 发现页网址: https://www.douyin.com/discover?modal_id=7069543727328398622
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import httpx

# Selenium imports (可选依赖)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.safari.options import Options as SafariOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Webdriver Manager (可选依赖)
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# Undetected ChromeDriver (可选依赖，用于绕过 WebDriver 检测)
try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROME_AVAILABLE = True
except ImportError:
    UNDETECTED_CHROME_AVAILABLE = False


# ── Cookie 文件解析 ─────────────────────────────────────

def load_cookie_from_file(cookie_file: str | Path) -> str:
    """从 Netscape Cookie 文件中提取抖音相关 Cookie

    支持浏览器插件（如 Cookie-Editor、EditThisCookie）导出的 cookies.txt 格式。
    格式: domain\\tinclude_subdomains\\tpath\\tsecure\\texpiry\\tname\\tvalue

    Args:
        cookie_file: cookies.txt 文件路径

    Returns:
        格式为 "key1=value1; key2=value2" 的 Cookie 字符串
    """
    cookie_path = Path(cookie_file)
    if not cookie_path.exists():
        return ""

    douyin_domains = {".douyin.com", "www.douyin.com", ".iesdouyin.com", "login.douyin.com"}
    cookies: list[str] = []

    with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain = parts[0].strip()
            name = parts[5].strip()
            value = parts[6].strip()

            # 检查是否是抖音域名
            is_douyin = False
            for d in douyin_domains:
                if domain == d or domain.endswith(d) or domain.endswith("douyin.com"):
                    is_douyin = True
                    break

            if is_douyin and name:
                cookies.append(f"{name}={value}")

    return "; ".join(cookies)


# ── 数据模型 ──────────────────────────────────────────────

@dataclass
class DouyinVideo:
    """解析后的抖音视频数据"""
    aweme_id: str = ""
    title: str = ""
    desc: str = ""
    author: str = ""
    author_id: str = ""
    # 无水印视频URL
    video_url: str = ""
    # 有水印视频URL（备用）
    video_url_watermark: str = ""
    # 封面图
    cover_url: str = ""
    # 视频文案/描述（作为字幕的补充）
    text_content: str = ""
    # 下载后的本地路径
    video_path: str = ""
    # 统计
    digg_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    # 原始数据
    raw_data: dict = field(default_factory=dict)


# ── URL 解析 ──────────────────────────────────────────────

# 匹配抖音短链接
_DOUYIN_SHORT_URL_RE = re.compile(
    r"https?://v\.douyin\.com/[A-Za-z0-9]+/?"
)
# 匹配抖音标准视频链接
_DOUYIN_VIDEO_URL_RE = re.compile(
    r"https?://(?:www\.)?douyin\.com/video/(\d+)"
)
# 匹配抖音发现页链接（modal_id 参数）
_DOUYIN_DISCOVER_URL_RE = re.compile(
    r"https?://(?:www\.)?douyin\.com/discover\?.*?modal_id=(\d+)"
)
# 匹配抖音笔记链接
_DOUYIN_NOTE_URL_RE = re.compile(
    r"https?://(?:www\.)?douyin\.com/note/(\d+)"
)
# 通用：从URL或文本中提取纯数字ID
_AWEME_ID_RE = re.compile(r"/video/(\d{10,})")
_MODAL_ID_RE = re.compile(r"modal_id=(\d{10,})")
_NOTE_ID_RE = re.compile(r"/note/(\d{10,})")
# 纯数字视频ID（直接输入aweme_id）
_PURE_AWEME_ID_RE = re.compile(r"^(\d{15,25})$")


def extract_urls_from_text(text: str) -> list[str]:
    """从分享文本中提取所有抖音URL"""
    urls: list[str] = []
    # 短链接
    urls.extend(_DOUYIN_SHORT_URL_RE.findall(text))
    # 标准视频链接
    urls.extend(_DOUYIN_VIDEO_URL_RE.findall(text))
    # 发现页链接
    urls.extend(_DOUYIN_DISCOVER_URL_RE.findall(text))
    # 笔记链接
    urls.extend(_DOUYIN_NOTE_URL_RE.findall(text))

    # 如果上面没匹配到，尝试用更宽泛的URL匹配
    if not urls:
        generic_url_re = re.compile(r"https?://[^\s<>\"]+douyin[^\s<>\"]*")
        urls.extend(generic_url_re.findall(text))

    return list(dict.fromkeys(urls))  # 去重保序


def extract_aweme_id_from_url(url: str) -> Optional[str]:
    """从URL中直接提取aweme_id（不需要网络请求）"""
    # 纯数字ID（用户直接输入aweme_id）
    m = _PURE_AWEME_ID_RE.match(url.strip())
    if m:
        return m.group(1)
    # /video/xxx
    m = _AWEME_ID_RE.search(url)
    if m:
        return m.group(1)
    # modal_id=xxx
    m = _MODAL_ID_RE.search(url)
    if m:
        return m.group(1)
    # /note/xxx
    m = _NOTE_ID_RE.search(url)
    if m:
        return m.group(1)
    return None


# ── 短链接解析 ────────────────────────────────────────────

def resolve_short_url(short_url: str, timeout: float = 15.0) -> Optional[str]:
    """解析抖音短链接，跟随重定向获取实际URL"""
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Mobile/15E148 Safari/604.1"
                ),
            },
        ) as client:
            resp = client.get(short_url)
            return str(resp.url)
    except Exception as e:
        print(f"[WARN] 短链接解析失败: {e}")
        return None


# ── 视频数据获取 ──────────────────────────────────────────

def _build_headers(cookie: str = "", user_agent: str = "") -> dict:
    """构建请求头"""
    ua = user_agent or (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    headers = {
        "User-Agent": ua,
        "Referer": "https://www.douyin.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _parse_render_data(html: str) -> Optional[dict]:
    """从HTML页面中提取 RENDER_DATA JSON"""
    # 方式1: <script id="RENDER_DATA" type="application/json">
    m = re.search(
        r'<script\s+id="RENDER_DATA"\s+type="application/json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if m:
        raw = m.group(1).strip()
        # RENDER_DATA 可能是 URL 编码的
        try:
            decoded = urllib.parse.unquote(raw)
            return json.loads(decoded)
        except (json.JSONDecodeError, Exception):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

    # 方式2: window.__RENDER_DATA__
    m = re.search(
        r"window\.__RENDER_DATA__\s*=\s*(\{.+?\})\s*;?\s*</script>",
        html,
        re.DOTALL,
    )
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 方式3: __NEXT_DATA__ (新版页面可能使用)
    m = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _extract_video_from_render_data(render_data: dict) -> Optional[DouyinVideo]:
    """从 RENDER_DATA 中提取视频信息"""
    video = DouyinVideo()

    # RENDER_DATA 结构通常是 dict，key 是某个hash，value 包含详情
    # 尝试递归查找 aweme_detail 或类似字段
    def _find_aweme_detail(obj, depth=0):
        if depth > 10:
            return None
        if isinstance(obj, dict):
            # 直接包含 aweme_detail
            if "aweme_detail" in obj:
                return obj["aweme_detail"]
            if "awemeDetail" in obj:
                return obj["awemeDetail"]
            # 递归查找
            for v in obj.values():
                result = _find_aweme_detail(v, depth + 1)
                if result:
                    return result
        return None

    detail = _find_aweme_detail(render_data)
    if not detail:
        return None

    return _build_video_from_detail(detail)


def _build_video_from_detail(detail: dict) -> DouyinVideo:
    """从 aweme_detail 构建DouyinVideo对象"""
    video = DouyinVideo()
    video.raw_data = detail

    video.aweme_id = str(detail.get("aweme_id", ""))
    video.desc = str(detail.get("desc", ""))
    video.title = video.desc  # 抖音没有独立标题，desc即标题
    video.text_content = video.desc

    # 作者信息
    author_info = detail.get("author", {})
    video.author = str(author_info.get("nickname", ""))
    video.author_id = str(author_info.get("unique_id", "") or author_info.get("uid", ""))

    # 统计信息
    stats = detail.get("statistics", {}) or detail.get("stats", {})
    video.digg_count = int(stats.get("digg_count", 0))
    video.comment_count = int(stats.get("comment_count", 0))
    video.share_count = int(stats.get("share_count", 0))

    # 视频URL - 优先无水印
    video_info = detail.get("video", {})
    play_addr = video_info.get("play_addr", {}) or video_info.get("playAddr", {})
    video.video_url = (
        play_addr.get("url_list", [None])[0]
        or play_addr.get("urlList", [None])[0]
        or ""
    )

    # 无水印：使用 play_addr_265 或 play_addr_h264 如果有
    for key in ("play_addr_265", "play_addr_h264", "play_addr"):
        addr = video_info.get(key, {})
        if addr and addr.get("url_list"):
            candidate = addr["url_list"][0]
            if candidate and "watermark" not in candidate:
                video.video_url = candidate
                break

    # 有水印备用
    download_addr = video_info.get("download_addr", {}) or video_info.get("downloadAddr", {})
    video.video_url_watermark = (
        download_addr.get("url_list", [None])[0]
        or download_addr.get("urlList", [None])[0]
        or ""
    )

    # 如果无水印URL没获取到，用有水印的
    if not video.video_url and video.video_url_watermark:
        video.video_url = video.video_url_watermark

    # 封面
    cover = video_info.get("cover", {}) or video_info.get("origin_cover", {})
    video.cover_url = (
        cover.get("url_list", [None])[0]
        or cover.get("urlList", [None])[0]
        or ""
    )

    return video


def fetch_video_via_page(
    aweme_id: str,
    cookie: str = "",
    user_agent: str = "",
    timeout: float = 15.0,
    debug: bool = False,
) -> Optional[DouyinVideo]:
    """通过抓取视频页面HTML来获取视频数据（SSR方式）"""
    url = f"https://www.douyin.com/video/{aweme_id}"
    headers = _build_headers(cookie, user_agent)

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[ERROR] 获取视频页面失败: {e}")
        return None

    # 调试：保存HTML以排查问题
    if debug or not _parse_render_data(html):
        debug_path = Path("debug_page.html")
        debug_path.write_text(html, encoding="utf-8")
        print(f"[DEBUG] 页面HTML已保存到 {debug_path.resolve()} (长度: {len(html)})")
        # 输出HTML中所有script标签的id，帮助排查
        script_ids = re.findall(r'<script[^>]*id="([^"]*)"', html)
        if script_ids:
            print(f"[DEBUG] 页面中的script id: {script_ids}")
        else:
            print("[DEBUG] 页面中没有带id的script标签，可能是CSR页面或验证页面")
        # 检查是否有验证码/登录墙
        if "验证" in html or "captcha" in html.lower() or "登录" in html:
            print("[DEBUG] 页面可能包含验证码或登录墙，Cookie可能无效")
        if len(html) < 2000:
            print(f"[DEBUG] 页面内容过短，可能被重定向: {html[:500]}")

    render_data = _parse_render_data(html)
    if not render_data:
        print("[WARN] 未能从页面提取RENDER_DATA，可能Cookie无效或页面结构变化")
        return None

    return _extract_video_from_render_data(render_data)


def fetch_video_via_web_api(
    aweme_id: str,
    cookie: str = "",
    user_agent: str = "",
    timeout: float = 15.0,
) -> Optional[DouyinVideo]:
    """通过抖音Web API获取视频详情（需要有效Cookie）

    使用抖音的 aweme/detail 接口直接获取JSON数据
    """
    url = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
    params = {
        "aweme_id": aweme_id,
        "aid": "6383",
        "cookie_enabled": "true",
        "platform": "PC",
        "downlink": "10",
    }
    ua = user_agent or (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    headers = {
        "User-Agent": ua,
        "Referer": f"https://www.douyin.com/video/{aweme_id}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[WARN] Web API请求失败: {e}")
        return None

    # 解析API响应
    if data.get("status_code") != 0:
        print(f"[WARN] Web API返回错误: status_code={data.get('status_code')}")
        return None

    aweme_detail = data.get("aweme_detail") or data.get("data", {}).get("aweme_detail")
    if not aweme_detail:
        print("[WARN] Web API响应中没有aweme_detail")
        return None

    return _build_video_from_detail(aweme_detail)


def fetch_video_via_mobile_api(
    aweme_id: str,
    timeout: float = 15.0,
) -> Optional[DouyinVideo]:
    """通过移动端API获取视频数据（无需Cookie，但信息可能不全）"""

    # 方式1: iesdouyin Web API（返回JSON）
    api_url = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"
    params = {"item_ids": aweme_id}
    mobile_ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    )

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": mobile_ua},
        ) as client:
            resp = client.get(api_url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("item_list") or []
                if items:
                    detail = items[0]
                    video = _build_video_from_detail(detail)
                    if video.aweme_id:
                        return video
    except Exception as e:
        print(f"[WARN] iesdouyin Web API失败: {e}")

    # 方式2: iesdouyin 分享页面
    url = f"https://www.iesdouyin.com/share/video/{aweme_id}"
    headers = {
        "User-Agent": mobile_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[WARN] 移动端分享页面请求失败: {e}")
        return None

    # 尝试从页面提取数据
    # iesdouyin 页面中的数据可能在 window._ROUTER_DATA 或 RENDER_DATA 中
    render_data = _parse_render_data(html)

    # 也尝试从 _ROUTER_DATA 提取
    if not render_data:
        m = re.search(
            r"window\._ROUTER_DATA\s*=\s*(\{.+?\})\s*</script>",
            html,
            re.DOTALL,
        )
        if m:
            try:
                render_data = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    if render_data:
        return _extract_video_from_render_data(render_data)

    # 最后尝试从页面直接提取视频URL
    video = DouyinVideo(aweme_id=aweme_id)
    # 尝试从 meta 标签获取描述
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    if m:
        video.desc = m.group(1)
        video.text_content = video.desc
        video.title = video.desc

    # 尝试提取视频URL
    video_url_match = re.search(
        r'playAddr["\']?\s*:\s*["\']?(https?://[^"\'<>\s]+)',
        html,
    )
    if video_url_match:
        video.video_url = video_url_match.group(1)

    # 尝试从 video 标签提取
    if not video.video_url:
        video_src_match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html)
        if video_src_match:
            video.video_url = video_src_match.group(1)

    return video if (video.desc or video.video_url) else None


def fetch_video_via_selenium(
    aweme_id: str,
    cookie: str = "",
    headless: bool = True,
    timeout: float = 30.0,
    browser: str = "auto",
    download_dir: Optional[str] = None,
    download_video: bool = False,
) -> Optional[DouyinVideo]:
    """通过 Selenium 浏览器自动化获取视频数据（绕过签名验证）

    Args:
        aweme_id: 视频ID
        cookie: Cookie字符串（可选）
        headless: 是否使用无头模式
        timeout: 页面加载超时时间
        browser: 浏览器类型 ("chrome", "safari", "auto")
        download_dir: 视频下载目录（可选）
        download_video: 是否在浏览器中下载视频

    Returns:
        DouyinVideo 对象，或 None
    """
    if not SELENIUM_AVAILABLE:
        print("[WARN] Selenium未安装，无法使用浏览器自动化")
        return None

    import platform

    url = f"https://www.douyin.com/video/{aweme_id}"
    print(f"[INFO] 使用 Selenium 浏览器自动化获取视频页面...")

    driver = None
    is_safari = False

    def _create_driver(browser_type: str) -> Optional[webdriver.WebDriver]:
        """创建 WebDriver，支持多种浏览器"""
        # 优先使用 undetected_chromedriver（能绕过 WebDriver 检测）
        if browser_type == "chrome" and UNDETECTED_CHROME_AVAILABLE:
            try:
                print("[INFO] 尝试使用 undetected_chromedriver（绕过检测）...")
                options = ChromeOptions()
                if headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--lang=zh-CN")
                if download_dir:
                    prefs = {"download.default_directory": download_dir}
                    options.add_experimental_option("prefs", prefs)

                driver = uc.Chrome(options=options, version_main=None)
                print("[INFO] 使用 undetected Chrome 浏览器")
                return driver
            except Exception as e:
                print(f"[WARN] undetected_chromedriver 初始化失败: {e}")

        if browser_type == "safari":
            # Safari WebDriver (macOS 内置，无需下载)
            try:
                options = SafariOptions()
                driver = webdriver.Safari(options=options)
                print("[INFO] 使用 Safari 浏览器")
                return driver
            except Exception as e:
                print(f"[WARN] Safari WebDriver 初始化失败: {e}")
                return None

        elif browser_type == "chrome":
            # 普通 Chrome WebDriver（可能被检测）
            try:
                options = ChromeOptions()
                if headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
                options.add_argument("--lang=zh-CN")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)
                # 设置下载目录
                if download_dir:
                    prefs = {"download.default_directory": download_dir}
                    options.add_experimental_option("prefs", prefs)

                if WEBDRIVER_MANAGER_AVAILABLE:
                    service = ChromeService(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    driver = webdriver.Chrome(options=options)
                print("[INFO] 使用普通 Chrome 浏览器")
                return driver
            except Exception as e:
                print(f"[WARN] Chrome WebDriver 初始化失败: {e}")
                return None

        return None

    # 尝试创建 WebDriver - 优先使用 Chrome（undetected）
    browsers_to_try = []
    if browser == "auto":
        # 优先尝试 Chrome（有 undetected_chromedriver 能绕过检测）
        browsers_to_try = ["chrome", "safari"]
    else:
        browsers_to_try = [browser]

    for b in browsers_to_try:
        driver = _create_driver(b)
        if driver:
            is_safari = (b == "safari")
            break

    if not driver:
        print("[ERROR] 无法初始化任何浏览器 WebDriver")
        return None

    try:
        # 设置超时
        driver.set_page_load_timeout(timeout)

        # 如果有 Cookie，先访问首页设置 Cookie
        if cookie:
            driver.get("https://www.douyin.com/")
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            for item in cookie.split("; "):
                if "=" in item:
                    name, value = item.split("=", 1)
                    try:
                        driver.add_cookie({
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": ".douyin.com"
                        })
                    except Exception:
                        pass
            print("[INFO] 已设置浏览器 Cookie")

        # 访问视频页面
        driver.get(url)

        # 等待页面加载完成
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # 等待视频元素出现
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
        except Exception:
            pass

        # 尝试点击播放按钮，触发真实视频加载
        try:
            # 查找播放按钮（多种可能的元素）
            play_buttons = driver.find_elements(By.CSS_SELECTOR, """
                [data-e2e='video-play'],
                .video-player,
                video,
                [class*='play'],
                [class*='Player']
            """)
            for btn in play_buttons:
                try:
                    btn.click()
                    time.sleep(2)  # 等待视频开始播放
                    break
                except Exception:
                    pass
        except Exception:
            pass

        # 等待一段时间让视频真正加载
        time.sleep(5)

        # 使用 JavaScript 监听并获取真实视频 URL
        real_video_url = None
        is_blob_url = False
        video_segment_urls = []

        try:
            # 方法1: 监听 video 标签的 currentSrc
            real_video_url = driver.execute_script("""
                var video = document.querySelector('video');
                if (video) {
                    return video.currentSrc || video.src;
                }
                return null;
            """)
            if real_video_url and 'uuu_' not in real_video_url and 'placeholder' not in real_video_url:
                is_blob_url = real_video_url.startswith('blob:')
                print(f"[INFO] 获取到视频 URL: {real_video_url[:80]}...")
                if is_blob_url:
                    print("[INFO] 这是一个 blob URL (流式视频)，需要进一步处理")

            # 方法2: 从 performance API 获取所有视频相关请求
            network_resources = driver.execute_script("""
                var entries = performance.getEntriesByType('resource');
                var urls = [];
                for (var i = 0; i < entries.length; i++) {
                    var url = entries[i].name;
                    // 过滤视频相关 URL
                    if (url.includes('.mp4') || url.includes('.m3u8') ||
                        url.includes('video') || url.includes('play') ||
                        url.includes('media') || url.includes('stream')) {
                        urls.push({
                            url: url,
                            type: entries[i].initiatorType,
                            size: entries[i].transferSize || 0
                        });
                    }
                }
                return urls;
            """)

            print(f"[INFO] 从 Performance API 获取到 {len(network_resources)} 个视频相关请求")

            # 找到真实的视频 URL（排除占位视频）
            for res in network_resources:
                url = res.get('url', '')
                if 'uuu_' not in url and 'placeholder' not in url:
                    # 优先选择 .mp4 URL
                    if '.mp4' in url and not url.startswith('blob:'):
                        print(f"[INFO] 找到 MP4 URL: {url[:100]}...")
                        real_video_url = url
                        is_blob_url = False
                        break
                    # 或者记录分段 URL
                    elif '.m3u8' in url or 'stream' in url:
                        video_segment_urls.append(url)

            if not real_video_url and video_segment_urls:
                print(f"[INFO] 找到视频流 URL: {video_segment_urls[0][:100]}...")

        except Exception as e:
            print(f"[WARN] 获取视频 URL 失败: {e}")

        # 获取页面 HTML
        html = driver.page_source

        # 初始化 video 对象
        video_obj: Optional[DouyinVideo] = None

        # 尝试从 RENDER_DATA 中获取数据
        try:
            render_data_str = driver.execute_script(
                "return document.querySelector('#RENDER_DATA')?.textContent || window.__RENDER_DATA__;"
            )
            if render_data_str:
                try:
                    decoded = urllib.parse.unquote(render_data_str)
                    render_data = json.loads(decoded)
                    video_obj = _extract_video_from_render_data(render_data)
                    if video_obj and not video_obj.aweme_id:
                        video_obj.aweme_id = aweme_id
                except (json.JSONDecodeError, Exception):
                    pass
        except Exception:
            pass

        # 从 HTML 解析
        if not video_obj or not video_obj.aweme_id:
            render_data = _parse_render_data(html)
            if render_data:
                video_obj = _extract_video_from_render_data(render_data)
                if video_obj and not video_obj.aweme_id:
                    video_obj.aweme_id = aweme_id

        # 如果还是没有，从页面元素提取
        if not video_obj:
            video_obj = DouyinVideo(aweme_id=aweme_id)

            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, "[data-e2e='video-desc']")
                if title_elem:
                    video_obj.desc = title_elem.text
                    video_obj.title = video_obj.desc
                    video_obj.text_content = video_obj.desc
            except Exception:
                pass

            if not video_obj.desc:
                try:
                    desc_elem = driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
                    if desc_elem:
                        video_obj.desc = desc_elem.get_attribute("content") or ""
                        video_obj.title = video_obj.desc
                        video_obj.text_content = video_obj.desc
                except Exception:
                    pass

        # 设置真实视频 URL
        if real_video_url and 'uuu_' not in real_video_url:
            video_obj.video_url = real_video_url

        # 如果需要下载视频，在关闭浏览器前下载
        if download_video and download_dir and video_obj and (video_obj.video_url or is_blob_url):
            print(f"[INFO] 开始在浏览器中下载视频...")
            download_path = Path(download_dir) / f"{aweme_id}.mp4"

            # 对于 blob URL，需要在浏览器内录制视频
            if is_blob_url:
                print("[INFO] 检测到 blob URL，使用浏览器录制方式下载...")
                try:
                    # 使用 JavaScript 录制 video 元素并导出
                    video_data = driver.execute_script("""
                        var video = document.querySelector('video');
                        if (!video) return null;

                        // 创建一个 canvas 来录制视频
                        var canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth || 640;
                        canvas.height = video.videoHeight || 480;
                        var ctx = canvas.getContext('2d');

                        // 播放视频并录制
                        video.currentTime = 0;
                        video.play();

                        // 等待视频准备好
                        return new Promise((resolve, reject) => {
                            var duration = video.duration || 10;
                            var fps = 15;
                            var frames = [];
                            var frameCount = 0;
                            var maxFrames = Math.floor(duration * fps);

                            function captureFrame() {
                                if (video.paused || video.ended || frameCount >= maxFrames) {
                                    // 视频结束，导出为 Blob
                                    // 注意：canvas 不能直接导出视频，只能导出图片
                                    // 我们返回一个提示，需要使用 MediaRecorder
                                    resolve({type: 'canvas_frames', frames: frameCount, duration: duration});
                                    return;
                                }
                                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                                frameCount++;
                                setTimeout(captureFrame, 1000 / fps);
                            }

                            video.onloadeddata = function() {
                                captureFrame();
                            };

                            // 如果视频已经在加载中
                            if (video.readyState >= 2) {
                                captureFrame();
                            }

                            // 超时处理
                            setTimeout(function() {
                                resolve({type: 'timeout', frames: frameCount});
                            }, 30000);
                        });
                    """)
                    print(f"[INFO] Canvas 录制结果: {video_data}")

                    # canvas 方式无法直接导出视频，需要用 MediaRecorder
                    # 尝试另一种方式：使用 MediaRecorder API
                    print("[INFO] 使用 MediaRecorder API 录制...")
                    result = driver.execute_script("""
                        var video = document.querySelector('video');
                        if (!video) return {error: 'no video element'};

                        return new Promise((resolve, reject) => {
                            try {
                                // 使用 captureStream
                                var stream = video.captureStream();
                                var mediaRecorder = new MediaRecorder(stream, {
                                    mimeType: 'video/webm;codecs=vp9'
                                });
                                var chunks = [];

                                mediaRecorder.ondataavailable = function(e) {
                                    if (e.data.size > 0) {
                                        chunks.push(e.data);
                                    }
                                };

                                mediaRecorder.onstop = function() {
                                    var blob = new Blob(chunks, {type: 'video/webm'});
                                    // 将 blob 转换为 ArrayBuffer 然后返回 base64
                                    var reader = new FileReader();
                                    reader.onloadend = function() {
                                        resolve({
                                            type: 'success',
                                            data: reader.result,  // base64
                                            size: blob.size
                                        });
                                    };
                                    reader.readAsDataURL(blob);
                                };

                                // 开始录制
                                video.currentTime = 0;
                                video.play();
                                mediaRecorder.start();

                                // 录制整个视频
                                setTimeout(function() {
                                    mediaRecorder.stop();
                                    video.pause();
                                }, (video.duration || 60) * 1000 + 1000);

                            } catch (err) {
                                resolve({error: err.toString()});
                            }
                        });
                    """)

                    if result and result.get('type') == 'success':
                        print(f"[INFO] MediaRecorder 录制成功，大小: {result.get('size')} bytes")
                        # 解析 base64 数据并保存
                        import base64
                        data_url = result.get('data', '')
                        if data_url.startswith('data:'):
                            # 去掉 data:video/webm;base64, 前缀
                            base64_data = data_url.split(',', 1)[1]
                            video_bytes = base64.b64decode(base64_data)
                            download_path.write_bytes(video_bytes)
                            print(f"[INFO] 视频已保存: {download_path}")
                            video_obj.video_path = str(download_path)
                        else:
                            print(f"[WARN] 数据格式异常: {data_url[:50]}...")
                    else:
                        print(f"[WARN] MediaRecorder 录制失败: {result}")

                except Exception as e:
                    print(f"[WARN] blob URL 下载失败: {e}")

            else:
                # 对于普通 URL，使用 fetch 下载
                try:
                    result = driver.execute_script("""
                        var videoUrl = arguments[0];
                        return fetch(videoUrl)
                            .then(response => {
                                if (!response.ok) throw new Error('HTTP ' + response.status);
                                return response.arrayBuffer();
                            })
                            .then(buffer => {
                                // 转换为 base64
                                var bytes = new Uint8Array(buffer);
                                var binary = '';
                                for (var i = 0; i < bytes.byteLength; i++) {
                                    binary += String.fromCharCode(bytes[i]);
                                }
                                return {type: 'success', data: btoa(binary), size: bytes.byteLength};
                            })
                            .catch(err => ({error: err.toString()}));
                    """, video_obj.video_url)

                    if result and result.get('type') == 'success':
                        print(f"[INFO] 视频下载成功，大小: {result.get('size') / 1024:.1f} KB")
                        import base64
                        video_bytes = base64.b64decode(result['data'])
                        download_path.write_bytes(video_bytes)
                        print(f"[INFO] 视频已保存: {download_path}")
                        video_obj.video_path = str(download_path)
                    else:
                        print(f"[WARN] 下载失败: {result}")

                except Exception as e:
                    print(f"[WARN] 视频下载失败: {e}")

        if video_obj.desc or video_obj.video_url:
            print(f"[INFO] Selenium 方式获取成功")
            return video_obj

        print("[WARN] Selenium 方式未能提取有效数据")
        return None

    except Exception as e:
        print(f"[ERROR] Selenium 浏览器自动化失败: {e}")
        return None

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ── 主入口 ────────────────────────────────────────────────

def parse_and_download_via_selenium(
    aweme_id: str,
    cookie: str = "",
    download_dir: str = "",
    timeout: float = 30.0,
) -> Optional[DouyinVideo]:
    """使用 Selenium 直接获取并下载视频（一站式方案）

    Args:
        aweme_id: 视频ID
        cookie: Cookie字符串
        download_dir: 下载目录
        timeout: 超时时间

    Returns:
        DouyinVideo 对象（包含下载路径），或 None
    """
    return fetch_video_via_selenium(
        aweme_id=aweme_id,
        cookie=cookie,
        headless=True,
        timeout=timeout,
        browser="auto",
        download_dir=download_dir,
        download_video=True,
    )


def parse_douyin_url(
    input_text: str,
    cookie: str = "",
    user_agent: str = "",
    timeout: float = 15.0,
) -> DouyinVideo:
    """解析抖音分享文本/URL，返回视频数据

    支持多种输入格式：
    - 分享口令
    - 短链接
    - 标准视频链接
    - 发现页链接

    Args:
        input_text: 抖音分享文本或URL
        cookie: 抖音网页Cookie（可选，有Cookie可获取更完整数据）
        user_agent: 自定义User-Agent
        timeout: 请求超时时间

    Returns:
        DouyinVideo 对象

    Raises:
        ValueError: 无法解析输入文本
        RuntimeError: 无法获取视频数据
    """
    input_text = input_text.strip()

    # 0. 先检查是否是纯数字视频ID
    aweme_id = extract_aweme_id_from_url(input_text)
    if aweme_id:
        print(f"[INFO] 检测到视频ID: {aweme_id}")
    else:
        # 1. 从文本中提取URL
        urls = extract_urls_from_text(input_text)
        if not urls:
            raise ValueError(f"无法从输入中提取抖音URL或视频ID: {input_text[:100]}")

        # 处理第一个URL
        url = urls[0]
        print(f"[INFO] 提取到URL: {url}")

        # 2. 提取aweme_id
        aweme_id = extract_aweme_id_from_url(url)

        # 3. 如果是短链接，需要先解析
        if not aweme_id and "v.douyin.com" in url:
            print("[INFO] 检测到短链接，正在解析...")
            resolved = resolve_short_url(url, timeout=timeout)
            if resolved:
                print(f"[INFO] 短链接解析结果: {resolved}")
                aweme_id = extract_aweme_id_from_url(resolved)
            else:
                raise RuntimeError(f"短链接解析失败: {url}")

        if not aweme_id:
            raise ValueError(f"无法从URL中提取视频ID: {url}")

    print(f"[INFO] 视频ID (aweme_id): {aweme_id}")

    # 4. 获取视频数据 - 多策略
    video: Optional[DouyinVideo] = None

    # 策略1: Web API（最可靠，需要Cookie）
    if cookie:
        print("[INFO] 策略1: 使用Web API获取视频详情（带Cookie）...")
        video = fetch_video_via_web_api(aweme_id, cookie, user_agent, timeout)

    # 策略2: 网页SSR
    if not video:
        print("[INFO] 策略2: 使用网页SSR方式获取视频数据...")
        video = fetch_video_via_page(aweme_id, cookie, user_agent, timeout)

    # 策略3: 移动端API（备用）
    if not video:
        print("[INFO] 策略3: 尝试移动端API...")
        video = fetch_video_via_mobile_api(aweme_id, timeout)

    # 策略4: Selenium 浏览器自动化（终极方案）
    if not video and SELENIUM_AVAILABLE:
        print("[INFO] 策略4: 使用 Selenium 浏览器自动化...")
        video = fetch_video_via_selenium(aweme_id, cookie=cookie, headless=True, timeout=timeout)

    if not video:
        raise RuntimeError(
            f"无法获取视频数据 (aweme_id={aweme_id})。"
            "请检查Cookie是否有效，或网络是否正常。"
        )

    # 确保aweme_id有值
    if not video.aweme_id:
        video.aweme_id = aweme_id

    print(f"[INFO] 视频标题: {video.title[:50]}..." if video.title else "[INFO] 视频标题: (无)")
    print(f"[INFO] 作者: {video.author}")
    print(f"[INFO] 视频URL: {'已获取' if video.video_url else '未获取'}")

    return video

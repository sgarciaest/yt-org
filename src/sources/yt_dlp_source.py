from domain.video import Video


# Planned implementation notes
# ─────────────────────────────
# yt-dlp can extract Watch Later using the browser's live session cookies,
# requiring no separate OAuth flow and no Google Cloud project.
#
# Command:
#   yt-dlp --cookies-from-browser chrome \
#          --flat-playlist \
#          --print "%(id)s\t%(title)s\t%(channel)s" \
#          "https://www.youtube.com/playlist?list=WL"
#
# Implementation sketch:
#   1. subprocess.run(["yt-dlp", ...], capture_output=True)
#   2. Parse tab-separated stdout lines into Video objects
#   3. Videos come with id + title + channel; enrichment adds tags/description
#
# Trade-offs:
#   + No OAuth flow; reads the browser session directly
#   + Works as long as the browser has an active YouTube session
#   - Requires yt-dlp to be installed (`pip install yt-dlp`)
#   - Cookies can expire; browser must be closed during extraction
#   - Technically scraping (check yt-dlp's terms for your use case)
#   - Browser choice is hardcoded (chrome) unless made configurable


class YtDlpSource:
    """Fetch Watch Later via yt-dlp with browser cookies.

    Not yet implemented. See module docstring for the planned approach.
    """

    @property
    def source_name(self) -> str:
        return "yt-dlp"

    def fetch(self) -> list[Video]:
        raise NotImplementedError(
            "--from-yt-dlp is not yet implemented.\n"
            "\n"
            "Planned: read Watch Later using yt-dlp and browser session cookies.\n"
            "See src/sources/yt_dlp_source.py for the full implementation plan.\n"
            "\n"
            "For now use: yt-org analyze --from-file <takeout_export.csv>"
        )

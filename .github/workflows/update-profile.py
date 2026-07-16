name: Update Profile SVG

on:
  schedule:
    - cron: "0 0 * * *"   # chạy 1 lần/ngày lúc 00:00 UTC (7h sáng giờ VN)
  push:
    branches: [main]
  workflow_dispatch: {}      # cho phép bấm chạy tay trong tab Actions

jobs:
  update-profile:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          clean: false   # tránh checkout cố xoá file cũ trong workspace và dính EACCES
                          # nếu file đó từng bị ghi bởi container Docker chạy quyền root

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Cài dependency
        run: pip install requests

      - name: Sinh github-stats.svg (tạm)
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GH_USERNAME: huanyd1
        run: python scripts/generate_stats.py

      - name: Sinh snake.svg (tạm)
        uses: Platane/snk@v3
        with:
          github_user_name: huanyd1
          outputs: |
            assets/snake.svg?color_snake=#38bdf8&color_dots=#1e293b,#0e4429,#006d32,#26a641,#39d353

      - name: Trả lại quyền sở hữu cho runner user
        # Platane/snk chạy trong Docker container, container có thể ghi file
        # bằng quyền root -> cần chown lại trước khi merge/git add/commit
        run: sudo chown -R $(id -u):$(id -g) assets/

      - name: Gộp terminal + stats + snake thành 1 file profile.svg
        run: python scripts/merge_profile.py

      - name: Xoá 2 file tạm, chỉ giữ profile.svg
        run: rm -f assets/github-stats.svg assets/snake.svg

      - name: Commit nếu có thay đổi
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add assets/profile.svg
          git add -A assets/  # đảm bảo git ghi nhận cả việc 2 file tạm đã bị xoá
          git diff --staged --quiet || git commit -m "chore: auto-update profile.svg"
          git push

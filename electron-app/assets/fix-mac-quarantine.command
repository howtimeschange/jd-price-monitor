#!/bin/bash
# 一键修复 macOS「已损坏」问题
APP="/Applications/JD Price Monitor.app"

echo "🔧 正在修复 JD Price Monitor..."

if [ ! -d "$APP" ]; then
  echo "❌ 未找到 /Applications/JD Price Monitor.app"
  echo "   请先将 App 拖入「应用程序」文件夹，再运行此脚本。"
  read -p "按回车键退出..."
  exit 1
fi

xattr -cr "$APP"
echo "✅ 修复完成！正在启动..."
open "$APP"

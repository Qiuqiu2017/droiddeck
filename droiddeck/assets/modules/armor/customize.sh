#!/system/bin/sh
# DroidDeck 防格机保护 - 安装脚本
ui_print "- 安装 DroidDeck 防格机保护"
ui_print "- 将拦截：rm/dd/mkfs/mke2fs/wipe/fastboot 等危险操作"
ui_print "- 保护分区：/  /data  /system  /vendor  /sdcard  /dev/block 等"

set_perm_recursive "$MODPATH/system/bin" 0 0 0755 0755

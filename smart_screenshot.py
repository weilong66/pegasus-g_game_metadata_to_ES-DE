import os
import sys
import tempfile
import subprocess

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def is_solid_color_frame(image_path, threshold=0.8):
    """
    检测画面是否为纯色（如黑屏、白屏、绿屏等）。
    
    Args:
        image_path: 图片路径
        threshold: 纯色占比阈值（0-1），超过此值则判定为纯色帧
    
    Returns:
        (bool, str): (是否为纯色帧, 主要颜色描述)
    """
    if not HAS_PIL:
        return False, "PIL未安装，无法检测"
    
    try:
        img = Image.open(image_path).convert('RGB')
        pixels = list(img.getdata())
        total_pixels = len(pixels)
        
        if total_pixels == 0:
            return True, "空图像"
        
        color_counts = {}
        for pixel in pixels:
            r, g, b = pixel
            rounded = (r // 10 * 10, g // 10 * 10, b // 10 * 10)
            color_counts[rounded] = color_counts.get(rounded, 0) + 1
        
        max_count = max(color_counts.values())
        max_ratio = max_count / total_pixels
        
        if max_ratio >= threshold:
            dominant_color = max(color_counts, key=color_counts.get)
            r, g, b = dominant_color
            
            if r < 25 and g < 25 and b < 25:
                color_name = "黑屏"
            elif r > 230 and g > 230 and b > 230:
                color_name = "白屏"
            elif g > 150 and r < 100 and b < 100:
                color_name = "绿屏"
            elif r > 150 and g < 100 and b < 100:
                color_name = "红屏"
            elif r < 100 and g < 100 and b > 150:
                color_name = "蓝屏"
            else:
                color_name = f"纯色({r},{g},{b})"
            
            return True, f"{color_name} ({max_ratio:.1%})"
        
        return False, f"画面正常 (主色占比: {max_ratio:.1%})"
    
    except Exception as e:
        return True, f"检测失败: {str(e)}"


def get_video_duration(video_path, ffmpeg_cmd='ffprobe'):
    """
    获取视频时长（秒）。
    
    Args:
        video_path: 视频文件路径
        ffmpeg_cmd: ffprobe 命令路径
        
    Returns:
        float: 视频时长（秒），获取失败返回 None
    """
    try:
        result = subprocess.run(
            [ffmpeg_cmd.replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0:
            duration = float(result.stdout.decode('utf-8').strip())
            return duration
    except Exception:
        pass
    return None


def extract_video_frame_with_fallback(video_path, output_image_path, target_time_sec=5,
                                      max_delay_sec=30, step_sec=1,
                                      solid_threshold=0.8, ffmpeg_cmd='ffmpeg', log_func=None):
    """
    从视频中提取帧，智能检测纯色帧并自动延后寻找正常画面。
    
    Args:
        video_path: 视频文件路径
        output_image_path: 输出图片路径
        target_time_sec: 目标截图时间（秒）
        max_delay_sec: 最大延后时间（秒），超过此时间则使用原时间点
        step_sec: 每次延后的步长（秒）
        solid_threshold: 纯色占比阈值（0.5-0.99），超过此值则判定为纯色帧
        ffmpeg_cmd: ffmpeg 命令路径
        log_func: 日志函数
    
    Returns:
        bool: 是否成功
    """
    if not os.path.isfile(video_path):
        if log_func:
            log_func(f"    视频文件不存在: {video_path}")
        return False
    
    try:
        max_delay_sec = float(max_delay_sec)
        step_sec = float(step_sec)
    except (ValueError, TypeError):
        max_delay_sec = 30.0
        step_sec = 1.0
    
    try:
        solid_threshold = float(solid_threshold)
        if solid_threshold < 0.5:
            solid_threshold = 0.5
        elif solid_threshold > 0.99:
            solid_threshold = 0.99
    except (ValueError, TypeError):
        solid_threshold = 0.8
    
    duration = get_video_duration(video_path, ffmpeg_cmd)
    if duration and target_time_sec >= duration:
        if log_func:
            log_func(f"    目标时间 {target_time_sec:.1f}s 超出视频时长 {duration:.1f}s")
        target_time_sec = max(0, duration - 1)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for attempt in range(int(max_delay_sec / step_sec) + 1):
            current_time = target_time_sec + attempt * step_sec
            
            if duration and current_time >= duration:
                if attempt > 0:
                    if log_func:
                        log_func(f"    到达视频末尾，使用最后尝试的时间点")
                current_time = max(0, duration - 0.5)
            
            temp_img = os.path.join(temp_dir, f"frame_{attempt}.png")
            
            try:
                result = subprocess.run(
                    [ffmpeg_cmd, '-y', '-ss', str(current_time), '-i', video_path,
                     '-f', 'image2', '-frames:v', '1', '-q:v', '2', temp_img],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if result.returncode != 0 or not os.path.isfile(temp_img):
                    if attempt == 0:
                        if log_func:
                            log_func(f"    截图失败: ffmpeg 返回错误")
                        return False
                    else:
                        continue
                
                if attempt == 0:
                    is_solid, desc = is_solid_color_frame(temp_img, solid_threshold)
                    if not is_solid:
                        shutil_move(temp_img, output_image_path)
                        if log_func:
                            log_func(f"    截图成功 @ {current_time:.1f}s ({desc})")
                        return True
                    else:
                        if log_func:
                            log_func(f"    检测到纯色帧 @ {current_time:.1f}s ({desc})，尝试延后...")
                else:
                    is_solid, desc = is_solid_color_frame(temp_img, solid_threshold)
                    if not is_solid:
                        shutil_move(temp_img, output_image_path)
                        if log_func:
                            log_func(f"    截图成功 @ {current_time:.1f}s ({desc})")
                        return True
                    else:
                        if log_func:
                            log_func(f"    检测到纯色帧 @ {current_time:.1f}s ({desc})，继续尝试...")
                
                if attempt * step_sec >= max_delay_sec:
                    shutil_move(temp_img, output_image_path)
                    if log_func:
                        log_func(f"    达到最大延后时间 ({max_delay_sec}s)，使用最后一帧 @ {current_time:.1f}s")
                    return True
            
            except Exception as e:
                if attempt == 0:
                    if log_func:
                        log_func(f"    截图异常: {str(e)}")
                    return False
    
    return False


def shutil_move(src, dst):
    """移动文件（使用 os.replace 以支持跨文件系统）"""
    import shutil
    shutil.move(src, dst)

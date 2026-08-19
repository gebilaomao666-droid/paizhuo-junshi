from vision_core import FrameSource, StableState, VisionState, pick_window


def test_stabilizer():
    st = StableState(3)
    a = VisionState(ok=True, hole=['As', 'Kh'], board=[], players=6, confidence=.9)
    assert not st.push(a).stable
    assert not st.push(a).stable
    assert st.push(a).stable
    b = VisionState(ok=True, hole=['As', 'Kh'], board=['Qh', 'Jh', '2c'], players=6, confidence=.9)
    assert not st.push(b).stable
    assert not st.push(b).stable
    assert st.push(b).stable
    print('OK: state stabilizer')


def test_pick_window():
    windows = [
        {'title': '普通窗口', 'width': 2000, 'height': 1200},
        {'title': 'AirDroid Cast - iPhone', 'width': 500, 'height': 900},
        {'title': 'AirDroid Cast', 'width': 700, 'height': 1000},
    ]
    # 多个匹配时取面积最大的一个
    assert pick_window(windows, ['AirDroid Cast'])['width'] == 700
    # 标题匹配不区分大小写
    assert pick_window(windows, ['airdroid cast'])['width'] == 700
    assert pick_window(windows, ['AIRDROID CAST'])['width'] == 700
    assert pick_window(windows, ['不存在']) is None
    print('OK: window picking')


def test_frame_source_modes():
    # 显式模式与设备别名
    assert FrameSource({'capture_mode': 'adb'}).candidate_modes() == ['adb']
    assert FrameSource({'capture_mode': 'window'}).candidate_modes() == ['window']
    assert FrameSource({'capture_mode': 'android'}).candidate_modes() == ['adb']
    assert FrameSource({'capture_mode': 'iphone'}).candidate_modes() == ['window']
    # auto：默认先 ADB 后投屏窗口；锁定投屏后优先复用投屏
    auto = FrameSource({'capture_mode': 'auto'})
    assert auto.candidate_modes() == ['adb', 'window']
    auto.active_mode = 'window'
    assert auto.candidate_modes() == ['window', 'adb']
    # 旧版 config.json 没有 capture_mode 字段时默认 auto
    assert FrameSource({}).candidate_modes() == ['adb', 'window']
    # 非法取值直接报错
    try:
        FrameSource({'capture_mode': 'usb'})
    except ValueError:
        pass
    else:
        raise AssertionError('capture_mode 非法值应当报错')
    print('OK: frame source modes')


def main():
    test_stabilizer()
    test_pick_window()
    test_frame_source_modes()
    print('OK: all smoke tests')


if __name__ == '__main__':
    main()

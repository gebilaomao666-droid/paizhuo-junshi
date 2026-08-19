from vision_core import StableState, VisionState


def main():
    st = StableState(3)
    a = VisionState(ok=True, hole=['As','Kh'], board=[], players=6, confidence=.9)
    assert not st.push(a).stable
    assert not st.push(a).stable
    assert st.push(a).stable
    b = VisionState(ok=True, hole=['As','Kh'], board=['Qh','Jh','2c'], players=6, confidence=.9)
    assert not st.push(b).stable
    assert not st.push(b).stable
    assert st.push(b).stable
    print('OK: state stabilizer')

if __name__ == '__main__':
    main()

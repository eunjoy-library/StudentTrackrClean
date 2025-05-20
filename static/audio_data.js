// 간단한 비프음 함수 구현
(function() {
    // AudioContext 인스턴스를 저장할 변수 (처음 클릭 시 생성)
    var audioCtx = null;
    
    // AudioContext 초기화 (사용자 제스처 필요)
    function initAudio() {
        if (!audioCtx) {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                console.log("오디오 시스템이 초기화되었습니다");
            } catch (e) {
                console.error("오디오 초기화 오류:", e);
            }
        }
        return audioCtx;
    }
    
    // 기본 비프음 생성 함수
    function beep(freq, duration, volume, type) {
        var ctx = initAudio();
        if (!ctx) return false;
        
        try {
            var oscillator = ctx.createOscillator();
            var gainNode = ctx.createGain();
            
            oscillator.type = type || 'sine';
            oscillator.frequency.value = freq;
            gainNode.gain.value = volume || 0.1;
            
            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);
            
            oscillator.start(ctx.currentTime);
            oscillator.stop(ctx.currentTime + (duration || 0.5));
            
            return true;
        } catch (e) {
            console.error("비프음 생성 오류:", e);
            return false;
        }
    }
    
    // 성공 소리 (띵동) - 더 낮은 주파수, 더 짧은 간격
    window.playSuccessSound = function() {
        try {
            // 첫 번째 음 (띵)
            beep(400, 0.15, 0.2, 'sine');
            
            // 두 번째 음 (동) - 0.15초 후
            setTimeout(function() {
                beep(600, 0.15, 0.2, 'sine');
            }, 150);
            
            console.log("성공 소리 재생");
            return true;
        } catch (e) {
            console.error("성공 소리 오류:", e);
            return false;
        }
    };
    
    // 오류 소리 (삐~)
    window.playErrorSound = function() {
        try {
            beep(700, 0.3, 0.2, 'sawtooth');
            console.log("오류 소리 재생");
            return true;
        } catch (e) {
            console.error("오류 소리 오류:", e);
            return false;
        }
    };
    
    // 페이지 로드 시 첫 클릭에서 오디오 컨텍스트 초기화
    document.addEventListener('click', function() {
        initAudio();
    }, { once: true });
    
    console.log("오디오 처리 모듈이 로드되었습니다");
})();
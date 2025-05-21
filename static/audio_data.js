// 간단한 비프음 함수 구현
// Web Audio API를 사용하여 직접 소리 생성
(function() {
    // 전역 변수로 AudioContext 선언
    var audioContext = null;
    
    // 오디오 컨텍스트 초기화 (사용자 인터랙션 필요)
    function initAudioContext() {
        if (!audioContext) {
            try {
                // 브라우저 호환성 처리
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log("오디오 컨텍스트가 초기화되었습니다.");
            } catch (e) {
                console.error("오디오 컨텍스트 생성 오류:", e);
            }
        }
        return audioContext;
    }
    
    // 성공 소리 재생 (띵동 소리)
    window.playSuccessSound = function() {
        var context = initAudioContext();
        if (!context) return;
        
        try {
            // 첫 번째 음 (띵)
            var oscillator1 = context.createOscillator();
            var gainNode1 = context.createGain();
            
            oscillator1.type = 'sine';
            oscillator1.frequency.value = 400; // 낮은 주파수
            
            gainNode1.gain.setValueAtTime(0, context.currentTime);
            gainNode1.gain.linearRampToValueAtTime(0.8, context.currentTime + 0.05); // 음량 증가 (0.6 → 0.8)
            gainNode1.gain.linearRampToValueAtTime(0, context.currentTime + 0.3);
            
            oscillator1.connect(gainNode1);
            gainNode1.connect(context.destination);
            
            oscillator1.start(context.currentTime);
            oscillator1.stop(context.currentTime + 0.3);
            
            // 두 번째 음 (동)
            var oscillator2 = context.createOscillator();
            var gainNode2 = context.createGain();
            
            oscillator2.type = 'sine';
            oscillator2.frequency.value = 600; // 첫 번째보다 높은 주파수
            
            gainNode2.gain.setValueAtTime(0, context.currentTime + 0.2);
            gainNode2.gain.linearRampToValueAtTime(0.8, context.currentTime + 0.25); // 음량 증가 (0.6 → 0.8)
            gainNode2.gain.linearRampToValueAtTime(0, context.currentTime + 0.5);
            
            oscillator2.connect(gainNode2);
            gainNode2.connect(context.destination);
            
            oscillator2.start(context.currentTime + 0.2);
            oscillator2.stop(context.currentTime + 0.5);
            
            console.log("성공 소리가 재생되었습니다.");
        } catch (e) {
            console.error("성공 소리 재생 오류:", e);
        }
    };
    
    // 오류 소리 재생 (삐- 경고음)
    window.playErrorSound = function() {
        var context = initAudioContext();
        if (!context) return;
        
        try {
            var oscillator = context.createOscillator();
            var gainNode = context.createGain();
            
            oscillator.type = 'sawtooth'; // 톱니파로 더 날카로운 경고음
            oscillator.frequency.value = 700; // 높은 주파수 삐- 소리
            
            gainNode.gain.setValueAtTime(0, context.currentTime);
            gainNode.gain.linearRampToValueAtTime(0.1, context.currentTime + 0.05); // 음량 조정 (0.2 → 0.1)
            gainNode.gain.linearRampToValueAtTime(0.1, context.currentTime + 0.3); // 음량 조정 (0.2 → 0.1)
            gainNode.gain.linearRampToValueAtTime(0, context.currentTime + 0.4);
            
            oscillator.connect(gainNode);
            gainNode.connect(context.destination);
            
            oscillator.start(context.currentTime);
            oscillator.stop(context.currentTime + 0.4);
            
            console.log("오류 소리가 재생되었습니다.");
        } catch (e) {
            console.error("오류 소리 재생 오류:", e);
        }
    };
    
    // 페이지 로드 시 첫 사용자 상호작용 후 오디오 컨텍스트 초기화
    document.addEventListener('click', function() {
        initAudioContext();
    }, { once: true });
    
    console.log("오디오 처리 모듈이 로드되었습니다.");
})();
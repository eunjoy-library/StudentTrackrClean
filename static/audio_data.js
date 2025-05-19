// Web Audio API를 사용한 소리 생성
let audioContext;

// 오디오 컨텍스트 초기화
function initAudioContext() {
    // 사용자 상호작용 이후 실행되어야 함
    if (!audioContext) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            console.log("오디오 컨텍스트가 초기화되었습니다.");
        } catch (e) {
            console.error("오디오 컨텍스트 생성 오류:", e);
        }
    }
    return audioContext;
}

// 성공 소리 재생 (높은 띵 소리)
function playSuccessSound() {
    const context = initAudioContext();
    if (!context) return;
    
    try {
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(1200, context.currentTime); // 높은 주파수
        oscillator.frequency.exponentialRampToValueAtTime(500, context.currentTime + 0.4); // 주파수 낮추기
        
        gainNode.gain.setValueAtTime(0, context.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.3, context.currentTime + 0.05);
        gainNode.gain.linearRampToValueAtTime(0, context.currentTime + 0.4);
        
        oscillator.connect(gainNode);
        gainNode.connect(context.destination);
        
        oscillator.start();
        oscillator.stop(context.currentTime + 0.4);
        
        console.log("성공 소리가 재생되었습니다.");
    } catch (e) {
        console.error("성공 소리 재생 오류:", e);
    }
}

// 오류 소리 재생 (낮은 똑딱 소리)
function playErrorSound() {
    const context = initAudioContext();
    if (!context) return;
    
    try {
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();
        
        oscillator.type = 'square';
        oscillator.frequency.setValueAtTime(150, context.currentTime); // 낮은 주파수
        oscillator.frequency.exponentialRampToValueAtTime(40, context.currentTime + 0.4); 
        
        gainNode.gain.setValueAtTime(0, context.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.3, context.currentTime + 0.05);
        gainNode.gain.linearRampToValueAtTime(0, context.currentTime + 0.4);
        
        oscillator.connect(gainNode);
        gainNode.connect(context.destination);
        
        oscillator.start();
        oscillator.stop(context.currentTime + 0.4);
        
        console.log("오류 소리가 재생되었습니다.");
    } catch (e) {
        console.error("오류 소리 재생 오류:", e);
    }
}

// 페이지 로드 시 사용자 상호작용 후 오디오 컨텍스트 초기화
document.addEventListener('click', function() {
    initAudioContext();
}, { once: true });

console.log("오디오 처리 모듈이 로드되었습니다.");
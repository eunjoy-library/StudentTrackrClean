// 오디오 파일 경로 지정
const successAudioPath = "/static/success.mp3";
const errorAudioPath = "/static/error.mp3";

// 오디오 객체 준비 함수
function playSuccessSound() {
    const audio = new Audio(successAudioPath);
    audio.play().catch(e => console.error('성공 오디오 재생 오류:', e));
}

function playErrorSound() {
    const audio = new Audio(errorAudioPath);
    audio.play().catch(e => console.error('오류 오디오 재생 오류:', e));
}

// 실행되는지 테스트 콘솔 로그
console.log("오디오 처리 모듈이 로드되었습니다.");
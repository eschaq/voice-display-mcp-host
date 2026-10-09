// Scale a card's content to the box it was given, downwards only.
//
// Measuring is done with the scale reset, because `.fit` is sized as the
// inverse of it and a measurement taken through a previous scale compounds.
// It loops because the two axes are coupled: a wider box wraps less text and
// can make the content shorter, which allows a bigger scale.
function fitToBand() {
  var shell = document.querySelector(".shell");
  var box = document.getElementById("fit");
  if (!shell || !box) return;
  var style = getComputedStyle(shell);
  var available =
    shell.clientHeight - parseFloat(style.paddingTop || 0) - parseFloat(style.paddingBottom || 0);
  if (!(available > 0)) return;
  var scale = 1;
  for (var pass = 0; pass < 3; pass += 1) {
    box.style.setProperty("--fit", String(scale));
    var needed = box.scrollHeight;
    if (!(needed > 0)) return;
    var next = Math.min(1, available / needed);
    next = Math.floor(next * 1000) / 1000;
    if (Math.abs(next - scale) < 0.002) break;
    scale = next;
  }
  box.style.setProperty("--fit", String(scale));
}
window.addEventListener("resize", fitToBand);

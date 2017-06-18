	var responsiveMenu = 0;
	$("#responsive-nav").click(function (e) {
		e.preventDefault();
		e.stopPropagation();
		if (!responsiveMenu) {
			$('#navbar-ul').animate({
				right: 0
			}, 300);
			responsiveMenu = 1;
		} else {
			$('#navbar-ul').animate({
				right: '-60%'
			}, 300);
			responsiveMenu = 0;
		}
	});
	$(window).resize(function (event) {

		if (responsiveMenu) {
			$('#navbar-ul').animate({
				right: '-60%'
			}, 300);
			responsiveMenu = 0;
		}
	});
	$(document).click(function () {
		if (responsiveMenu) {
			$('#navbar-ul').animate({
				right: '-60%'
			}, 300);
			responsiveMenu = 0;
		}
	});
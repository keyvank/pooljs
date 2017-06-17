		var gulp 			 = require('gulp');
		sass 		 = require('gulp-sass'),
		postcss  = require('gulp-postcss'),
		imagemin 	 = require('gulp-imagemin'),
		autoprefixer = require('gulp-autoprefixer'),
		minify		 = require('gulp-minify-css'),
		concat 		 = require('gulp-concat');


gulp.task('css', function () {
	return gulp.src('css/*.css')
	.pipe(autoprefixer())
		.pipe(concat('all.css'))
		.pipe(gulp.dest('css'));
});
gulp.task('js', function () {
	return gulp.src('js/*.js')
		.pipe(concat('all.js'))
		.pipe(gulp.dest('js'));
});

gulp.task('sass', function () {
  return gulp.src('sass/*.scss')
    .pipe(sass().on('error', sass.logError))
		.pipe(autoprefixer({ browsers: ['last 2 versions'] }))
    .pipe(gulp.dest('css'));
});

gulp.task('sass:watch', function () {
  gulp.watch('sass/*.scss', ['sass']);
});

gulp.task('img', function(){
	gulp.src('img/*')
		.pipe(imagemin({progressive: true}))
		.pipe(gulp.dest('img'));
});

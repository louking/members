const gulp = require('gulp');
const nunjucks = require('gulp-nunjucks');

exports.default = () => (
	gulp.src('templates/*.njk')
		.pipe(nunjucks.precompile())
		.pipe(gulp.dest('nunjucks'))
);
'use strict';

var fs = require('fs');
var Promise = require('bluebird');
var chai = require('chai');
var chaiAsPromised = require('chai-as-promised');

chai.use(chaiAsPromised);
chai.should();

var m3u = require('../m3u');

var files = ['extended', 'invalid_extended']
                .map(function (filename) { return fs.readFileSync(__dirname + '/playlists/' + filename + '.m3u'); });

describe('M3U playlist parser', function () {
    it('should be rejected when invalid data passed', function () {
        return Promise.all([
            m3u.parse().should.eventually.be.rejected,
            m3u.parse(123).should.eventually.be.rejected,
            m3u.parse('invalid').should.eventually.be.rejected,
            m3u.parse(files[1]).should.eventually.be.rejected,
            m3u.parse('#EXTM3U\n\ninvalid').should.eventually.be.rejected
        ]);
    });

    describe('extended format', function () {
        it('should return array with playlist items', function () {
            return m3u.parse(files[0])
                .then(function (data) {
                    return Promise.all([
                        data.should.be.an.instanceOf(Array),
                        data.should.have.length(5),
                        data[0].should.be.an('object'),
                        data[0].should.have.all.keys('file', 'title', 'duration'),
                        data[0].duration.should.be.equal(123),
                        data[0].title.should.be.equal('Sample artist - Sample title'),
                        data[0].file.should.be.equal('Sample.mp3')
                    ]);
                });
        });

        it('should parse negative duration properly', function () {
            return m3u.parse(files[ 0 ]).should.be.eventually.fulfilled
                .and.have.deep.property('[4].duration', -1);
        });
    });
});

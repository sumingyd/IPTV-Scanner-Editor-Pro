var Promise = require('bluebird');

function parse (data) {
    if (Buffer.isBuffer(data))
        data = data.toString();
    else if (typeof data !== 'string')
        return Promise.reject(new TypeError('Data passed to the parser should be a string'));

    return new Promise(function (resolve, reject) {
        data = data.split('\n')
            .filter(function (str) {
                return str.length > 0;
            });

        if (data.shift().trim() !== '#EXTM3U')
            return reject(new Error('Passed data is not valid M3U playlist'));

        var buffer = [], isWaitingForLink = false, line;

        while ((line = data.shift())) {
            line = line.trim();

            if (isWaitingForLink) {
                buffer[buffer.length - 1].file = line;
                isWaitingForLink = false;
            } else if (line.slice(0, 7) === '#EXTINF') {
                var result = /^#EXTINF:(-?)(\d+),(.*)$/.exec(line);
                if (!result)
                    throw new Error('Invalid M3U format');

                buffer.push({
                    title:    result[3].trim(),
                    duration: +(result[1] + result[2].trim())
                });

                isWaitingForLink = true;
            } else {
                throw new Error('Invalid data');
            }
        }

        resolve(buffer);
    });
}

module.exports.parse = parse;

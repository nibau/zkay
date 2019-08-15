module.exports = function(callback) {
    var assert = require('assert');

    var Verifier = artifacts.require('Verifier');
    var account0 = web3.eth.accounts[0];

    var A = ['0x271d87916459e1288dfcab818e292c7d06061a5c994f036243510ee9cb9423ae',
    '0xc80501da6f9cf0945a87811f9783118070ed26e7f72cb9f4a27cb042450acb5']
    var A_p = ['0x7ba62bcda05b603b18142469edd4adc1e933ea0ac8cd8cd3fec6a1ec94ade15',
    '0x178f51b31f7c8086f74a6d90be6845d1c7cf614c2fac1dfdae5d5ccd73e3afd9']
    var B = [['0x2a835fe82a750bc2d7e89f6200c6eb4726555eeab03a59b0274af5d97d3a5eb4', 
    '0x20ad076aafad93ba9808c62074fff7ee94d9d141c1b104c6f19ba17c39c14b98'], 
    ['0x10874f3eaae67dba4221a713cdd351ce306322a677352eb3a447b715c5b9c466', 
    '0x1a8421aebbb287246061e69bc82f5ac1985ca58957e437039f3861bce88aecd4']]
    var B_p = ['0x2c8cca60a1dd32ad9027d8ba95b207b1c724b3e8b9ce6821bfe8f362d6980f97', 
    '0x2c5ba421d16805dc837dcf2688e9eae9adcc4a12efddaccded35a45cf515dd38']
    var C = ['0x2ba8f195a8f52cd55c40a6faee3aaf703e382e657b8ccc2faeaef6ac9de9fd0e', 
    '0xe5cfc8ad0fac863ebc60377e6d937253a19b34394e7b82ed88b7b7a26167f2b']
    var C_p = ['0x1258394c2927d0a2cd3df024dd566d7b38ce4de82127b62e14ff6c41623af079', 
    '0xdc34c889d6af59a4679d3a5b18176efc53a9e831fec8f1ced29a3c461f57927']
    var H = ['0x103159ec7fc38b06d4e36569a5b645263b3a2b530277fb3d69f593cc5739fb5', 
    '0x2abfd3ce7e64d470801591cd731d65c13105bf5eefdae5a39004f5ab969745cd']
    var K = ['0x25bb69853ba9e06bb625a609ff0a34bab333f7fa22bdd8c2a912174434cd041a', 
    '0x2d0537e05858d6f34f1fefd342e42610e5049dad2145445ac5a5f0c8aa945f27']

    
    var output = ['15', '1']

    Verifier.deployed().then(function(instance) {
        assert(instance != undefined);

        console.log("Verifier deployed; trying to submit proof.")

        instance.verifyTx.call(
            A,
            A_p,
            B,
            B_p,
            C,
            C_p,
            H,
            K,
            output,
            {
                from: account0,
            }
        ).then(function(result) {
            console.log("Success: proof verification did no raise an error!");
            console.log("Verification result:", result);
        }, function(err) {
            console.log("Failure: proof verification raised an error!");
            console.log(err);
        });
    });

    callback(); // I don't really understand what the callback is for; apparently you can pass
                // an error message but it did not really work when I tried it
}

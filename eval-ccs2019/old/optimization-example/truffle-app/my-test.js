proof = {
    A :["0x11c26d16970ebd76162d92e844036592d8c352c04647172a0f6784ea2b64454b", "0xd3ed30e17e093967ca96b573a35dc78a59bd754ffae171c5095a2ddac60887e"],
    A_p:["0x118d9decb90caa8a167c5ef7ce7a97c8660578e6dc0789e863af73e0c204c96d", "0x2626b563dd7b01c2fdf46f72597338670d2ef9876a747598a601952c6db187a0"],
    B:
        [["0x16974ad2255f664e1981f7970db24521fedbe6153ce33b04cfebb09db808e0bc", "0xbc295db6638af810c05c9a58847dce0beeb21106880fd7e18c85cfd6aa1fb53"], ["0x2e2f069d41776327d70d958dc285d8237285cb03b479d6be9aab4e57c430ddf3", "0x25193ddc083c302e46c477aa7960541b89277e6e1ec4c7f1790562a3f3ab6d84"]],
    
    B_p:["0x29c4a0f9d407731833a489865252369c3743081a1756407847eabeea1a658264", "0xb0889f2d0aa5315290ef450eee2d11c4f270f2e3e7702654d161454c4f91629"],
    C:["0x1895a9a5b963863eb39c6c6623a41a3734fab9a8092cf0ce8cab054f17201c7b", "0x5c510168beccb2e51b21ad859c862d7ae4dfe1eaaa11e16c063aa76b95ea2f5"],
    C_p:["0x41a7d7a8c76bb76959bc58f9b2744d751870f95f52a608b7b12188e5beab553", "0x1d30b46f9b44690232b836e803c80aa691951c553e744b5775b6db8dbe778f54"],
    H:["0xc69f69fd027b905c35bfd2dd7b845472c9452865e6abe0b3a2e8251e4a79d90", "0x27e653a8f7b9c34017d3a61cff11e45d3277f63d30cf16cb57870a4d81ace339"],
    K:["0xb7a42a1411f681910dd80cf1336956b691d01fd48e8d31fe7eae842ea29cb9a", "0x16c7c03f53fcd32996b9174a8a086facc5bcd38e24ef3accb280f1b20ca884b7"],
 	input:[113569,1]
}


proof_arr = ["0x11c26d16970ebd76162d92e844036592d8c352c04647172a0f6784ea2b64454b", "0xd3ed30e17e093967ca96b573a35dc78a59bd754ffae171c5095a2ddac60887e", "0x118d9decb90caa8a167c5ef7ce7a97c8660578e6dc0789e863af73e0c204c96d", "0x2626b563dd7b01c2fdf46f72597338670d2ef9876a747598a601952c6db187a0", "0x16974ad2255f664e1981f7970db24521fedbe6153ce33b04cfebb09db808e0bc", "0xbc295db6638af810c05c9a58847dce0beeb21106880fd7e18c85cfd6aa1fb53", "0x2e2f069d41776327d70d958dc285d8237285cb03b479d6be9aab4e57c430ddf3", "0x25193ddc083c302e46c477aa7960541b89277e6e1ec4c7f1790562a3f3ab6d84", "0x29c4a0f9d407731833a489865252369c3743081a1756407847eabeea1a658264", "0xb0889f2d0aa5315290ef450eee2d11c4f270f2e3e7702654d161454c4f91629", "0x1895a9a5b963863eb39c6c6623a41a3734fab9a8092cf0ce8cab054f17201c7b", "0x5c510168beccb2e51b21ad859c862d7ae4dfe1eaaa11e16c063aa76b95ea2f5", "0x41a7d7a8c76bb76959bc58f9b2744d751870f95f52a608b7b12188e5beab553", "0x1d30b46f9b44690232b836e803c80aa691951c553e744b5775b6db8dbe778f54", "0xc69f69fd027b905c35bfd2dd7b845472c9452865e6abe0b3a2e8251e4a79d90", "0x27e653a8f7b9c34017d3a61cff11e45d3277f63d30cf16cb57870a4d81ace339", "0xb7a42a1411f681910dd80cf1336956b691d01fd48e8d31fe7eae842ea29cb9a", "0x16c7c03f53fcd32996b9174a8a086facc5bcd38e24ef3accb280f1b20ca884b7"];


module.exports = async function(callback) {
    var assert = require('assert');
    
    var Test = artifacts.require('Test');
    var Verifier = artifacts.require('Verifier');
    let accounts = await web3.eth.getAccounts();
    
    Test.deployed().then(function(instance) {
        assert(instance != undefined);

        instance.f(
            proof_arr,
            proof_arr,
            proof_arr,
            proof_arr,
            {
                from: accounts[1]
            }
        ).then(function(result) {
            console.log("TX successful: Called function f successful.")
            console.log("Gas used:", result['receipt']['gasUsed']);
        }, function(err) {
            console.log("TX failed: Could not call function f.")
            console.log(err);
        });

    });

    callback(); // I don't really understand what the callback is for; apparently you can pass
                // an error message but it did not really work when I tried it
}

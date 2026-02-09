const hre = require("hardhat");

async function main() {
    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying contracts with account:", deployer.address);

    const MockBTC = await hre.ethers.getContractFactory("MockCollateralToken");
    const mockBTC = await MockBTC.deploy();
    await mockBTC.deployed();
    console.log("MockBTC:", mockBTC.address);

    const MockOracle = await hre.ethers.getContractFactory("MockPriceOracle");
    const initialPrice = hre.ethers.utils.parseEther("50000");
    const mockOracle = await MockOracle.deploy(initialPrice);
    await mockOracle.deployed();
    console.log("MockOracle:", mockOracle.address);

    const FToken = await hre.ethers.getContractFactory("FToken");
    const fToken = await FToken.deploy("fBTC", "fBTC");
    await fToken.deployed();
    console.log("FToken:", fToken.address);

    const SToken = await hre.ethers.getContractFactory("ShortToken");
    const sToken = await SToken.deploy("sBTC", "sBTC");
    await sToken.deployed();
    console.log("SToken:", sToken.address);

    const ShortVault = await hre.ethers.getContractFactory("ShortVaultV2");
    const vault = await ShortVault.deploy(
        mockBTC.address,
        fToken.address,
        sToken.address,
        mockOracle.address,
        hre.ethers.utils.parseEther("1.05"),
        hre.ethers.utils.parseEther("1.0")
    );
    await vault.deployed();
    console.log("ShortVaultV2:", vault.address);

    await (await fToken.setVault(vault.address)).wait();
    await (await sToken.setVault(vault.address)).wait();

    await (await mockBTC.mint(hre.ethers.utils.parseEther("10"))).wait();
    await (await mockBTC.approve(vault.address, hre.ethers.utils.parseEther("10"))).wait();
    await (await vault.mint(hre.ethers.utils.parseEther("1"))).wait();

    const fs = require('fs');
    fs.writeFileSync('deployment-info.json', JSON.stringify({
        mockBTC: mockBTC.address,
        mockOracle: mockOracle.address,
        fToken: fToken.address,
        sToken: sToken.address,
        vault: vault.address,
        deployer: deployer.address
    }, null, 2));

    console.log("\n✅ Deployment completed!");
}

main().catch(console.error);

{
  description = "Ardent Forge — NixOS configuration for Bee Link";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Thomas's dotfiles for dev environment
    dotfiles = {
      url = "github:t-eckert/dotfiles";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, dotfiles }:
    let
      locals = import ./locals.nix;
    in {
    nixosConfigurations.ardent-forge = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = { inherit dotfiles locals; };
      modules = [
        ./hardware.nix
        ./configuration.nix
        home-manager.nixosModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {
              inherit dotfiles;
              isDarwin = false;
              isLinux = true;
            };
            users.thomaseckert = import ./home.nix;
          };
        }
      ];
    };
  };
}

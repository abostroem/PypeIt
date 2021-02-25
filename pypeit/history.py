"""
Module for managing the history of PypeIt output files.

.. include common links, assuming primary doc root is up one directory
.. include:: ../include/links.rst
"""

import os.path

from astropy.time import Time
from pypeit.core.framematch import FrameTypeBitMask

class History:
    """
    Holds and creates history entries for FITS files.

    Args:

    header (:obj:`astropy.io.fits.Header`, optional):
        Header from a fits file. The
        history keyword entries in this header will be used to populate this 
        History object. Defaults to None.

    Attributes:
    
    history (obj::`list` of `str`): List of history entries.
    """

    def __init__(self, header=None):
        """
        Initializes history.
        """
        self.history = []
        if header is not None and 'HISTORY' in header:
            for card in header['HISTORY']:
                self.history.append(str(card))

    def add_reduce(self, calib_id, metadata, frames, bg_frames):
        """
        Add history entries for reducing a frame.

        Args:
        calib_id (int): The calibration id being reduced.

        metadata (:obj:`pypeit.metadata.PypeItMetadata`): The metadata for all
            the fits files PypeIt knows of.

        frames (:obj:`numpy.ndarray`): Array of indexes into metadata of the 
            frames being combined in the reduction.

        bg_frames (:obj:`numpy.ndarray`): Array of indexes into metadata of the 
            frames being subtracted in the reduction.
        """
        self.append(f'PypeIt Reducing target {metadata["target"][frames[0]]}')
        self.append('Combining frames:', add_date=False)
        for frame in frames:
            self.append(f'"{metadata["filename"][frame]}"', add_date=False)
        if len(bg_frames) > 0:
            self.append('Subtracted background from frames:', add_date=False)
            for frame in bg_frames:
                self.append(f'"{metadata["filename"][frame]}"', add_date=False)

        frametype_bitmask = FrameTypeBitMask()
        calibration_types = [x for x in frametype_bitmask.keys() if x not in ['science', 'standard']]

        calib_frames = metadata[metadata.find_frames(calibration_types, calib_id)]
        if len(calib_frames) > 0:
            self.append('Callibration frames:', add_date=False)

            for frame in calib_frames:
                self.append(f'{frame["frametype"]} "{frame["filename"]}"', add_date=False)

    def add_coadd1d(self, spec1d_files, objids):
        """
        Add history entries for 1D coadding.
        
        The history shows what files and objects were used for coadding.
        To save characters the unique files are listed first and then the
        objects are listed. For example:
        HISTORY 2021-01-23T02:12 PypeIt Coadded 4 objects from 3 spec1d files           
        HISTORY File 0 "spec1d_DE.20170425.53065-dra11_DEIMOS_2017Apr25T144418.240.fits"  
        HISTORY File 1 "spec1d_DE.20170425.51771-dra11_DEIMOS_2017Apr25T142245.350.fits"  
        HISTORY File 2 "spec1d_DE.20170425.50487-dra11_DEIMOS_2017Apr25T140121.014.fits"  
        HISTORY Object ID SPAT0692-SLIT0704-DET08 from file 0                           
        HISTORY Object ID SPAT0695-SLIT0706-DET04 from file 2                           
        HISTORY Object ID SPAT0691-SLIT0704-DET08 from file 2                           
        HISTORY Object ID SPAT0695-SLIT0706-DET04 from file 1

        Args:
        spec1d_files (:obj:`list`): List of the spec1d files used for coadding.
        objids (:obj:`list`): List of the PypeIt object ids used in coadding.
        """

        combined_file_obj = zip(spec1d_files, objids)
        unique_files = list(set(spec1d_files))
        history_list = [(unique_files.index(x), y) for x, y in combined_file_obj]
        self.append(f'PypeIt Coadded {len(history_list)} objects from {len(unique_files)} spec1d files')
        for i in range(len(unique_files)):
            self.append(f'File {i} "{os.path.basename(unique_files[i])}"', add_date=False)

        for file_index, objid in history_list:
            self.append(f'Object ID {objid} from file {file_index}', add_date=False)


    def append(self, history, add_date=True):
        """Append a new history entry.

        Args: 
        history (str): The history text to add.

        add_date (bool): If true a isot formatted date willbe prepended
            to the history entry. Defaults to True.
        """

        if add_date:
            self.history.append(f'{Time.now().to_value("isot", subfmt="date_hm")} {history}')
        else:
            self.history.append(history)
        
    def write_to_header(self, header):
        """Write history entries to a FITS header
        Args:
        header (`astropy.io.fits.Header`): The header to write to.
        """
        
        for line in self.history:
            header['history'] = line

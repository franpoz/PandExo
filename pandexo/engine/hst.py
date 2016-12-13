import numpy as np
import pandas as pd
"""
ToDo:
    write another function to predict (nsamp, samp_seq, norbits) if values aren't given
"""
def wfc3_GuessNOrbits(trdur):
    '''
    Predict number of HST orbits for transit observation when not provided by the user.
    Written by Kevin Stevenson      October 2016
    :param trdur: transit duration in seconds
    :type trdur: float
    :returns: norbits--number of requested orbits per transit (including discarded thermal-settling orbit)
    :rtype: float    
    '''
    # Compute # of HST orbits during transit
    # ~96 minutes per HST orbit
    orbitsTr    = trdur/96./60.
    if orbitsTr <= 1.5:
        norbits = 4.
    elif orbitsTr <= 2.0:
        norbits = 5.
    else:
        norbits = np.ceil(orbitsTr*2+1)
    
    return norbits

def wfc3_GuessParams(hmag, disperser, scanDirection, subarray, obsTime,maxExptime=150.):
    '''
    Predict nsamp and samp_seq when values not provided by the user.
    Written by Kevin Stevenson      October 2016

    :param hmag: H-band magnitude
    :param disperser: grism (G141 or G102)
    :param scanDirection: spatial scan direction (Forward or Round Trip)
    :param subarray: subarray aperture (grism256 or grism512)
    :param obsTime: available observing time per HST orbit in seconds
    :param maxExptime: (optional) default=150.0, maximum exposure time in seconds
    :type hmag: float
    :type disperser: str
    :type scanDirection: str
    :type subarray: str
    :type obsTime: float
    :type maxExptime: float
    :retruns: nsamp, samp_seq
        nsamp--number of up-the-ramp samples (1..15)
        samp_seq--time between non-destructive reads
    :rtype: float, string
    '''
    allnsamp    = np.arange(1,16)
    allsampseq  = ['spars5', 'spars10', 'spars25']
    maxDutyCycle= 0
    for samp_seq in allsampseq:
        for nsamp in allnsamp:
            exptime, tottime, scanRate, scanHeight, fluence = wfc3_obs(hmag, disperser, scanDirection, 
                                                                       subarray, nsamp, samp_seq)
            # Compute duty cycle and compare
            # Exposure time should be less than 2.5 minutes to achieve good time resolution
            ptsOrbit    = np.floor(obsTime/tottime)
            dutyCycle   = (exptime*(ptsOrbit-1))/50./60*100
            if (dutyCycle > maxDutyCycle) and (exptime < maxExptime):
                maxDutyCycle    = dutyCycle
                bestsampseq     = samp_seq
                bestnsamp       = nsamp
    
    return bestnsamp, bestsampseq

def wfc3_obs(hmag, disperser, scanDirection, subarray, nsamp, samp_seq):
    '''
    Determine the recommended exposure time, scan rate, scan height, and overheads.
    Written by Kevin Stevenson      October 2016
    PARAMETERS
    ----------
    :param hmag: H-band magnitude
    :param disperser: grism (G141 or G102)
    :param scanDirection: spatial scan direction (Forward or Round Trip)
    :param subarray: subarray aperture (grism256 or grism512)
    :param nsamp: number of up-the-ramp samples (1..15)
    :param samp_seq: time between non-destructive reads (SPARS5, SPARS10, or SPARS25)
    :returns:
        exptime--exposure time in seconds(float)
        tottime--total frame time including overheads in seconds(float)
        scanRate--recommented scan rate in arcsec/s(float)
        scanHeight--scan height in pixels(float)
        fluence--maximum pixel fluence in electrons(float)
    :rtype: float,float,float,float,float 
    '''
    # Estimate exposure time
    if subarray == 'grism512':
        # GRISM512
        if samp_seq == 'spars5':
            exptime     = 0.853 + (nsamp-1)*2.9215  #SPARS5
        elif samp_seq == 'spars10':
            exptime     = 0.853 + (nsamp-1)*7.9217  #SPARS10
        elif samp_seq == 'spars25':
            exptime     = 0.853 + (nsamp-1)*22.9213 #SPARS25
        else:
            print("****HALTED: Unknown SAMP_SEQ: %s" % samp_seq)
            return
    else:
        # GRISM256
        if samp_seq == 'spars5':
            exptime     = 0.280 + (nsamp-1)*2.349   #SPARS5
        elif samp_seq == 'spars10':
            exptime     = 0.278 + (nsamp-1)*7.3465  #SPARS10
        elif samp_seq == 'spars25':
            exptime     = 0.278 + (nsamp-1)*22.346  #SPARS25
        else:
            print("****HALTED: Unknown SAMP_SEQ: %s" % samp_seq)
            return
    
    # Recommended scan rate
    scanRate    = np.round(1.9*10**(-0.4*(hmag-5.9)),3)     #arcsec/s
    if disperser == 'g102':
        # G102/G141 flux ratio is ~0.8
        scanRate *= 0.8
    # Max fluence in electrons/pixel
    fluence     = (5.5/scanRate)*10**(-0.4*(hmag-15))*2.4   #electrons
    if disperser == 'g102':
        # WFC3_ISR_2012-08 states that the G102/G141 scale factor is 0.96 DN/electron
        fluence *= 0.96
        # G102/G141 flux ratio is ~0.8
        fluence *= 0.8
    # Scan height in pixels
    scanRatep   = scanRate/0.121                            #pixels/s
    scanHeight  = scanRatep*exptime                         #pixels
    '''
    #Quadratic correlation between scanRate and read overhead
    foo     = np.array([0.0,0.1,0.3,0.5,1.0,2.0,3.0,4.0])/0.121
    bar     = np.array([ 40, 40, 41, 42, 45, 50, 56, 61])
    c       = np.polyfit(foo,bar,2)
    model   = c[2] + c[1]*foo + c[0]*foo**2
    #c = [  6.12243227e-04,   6.31621064e-01,   3.96040946e+01]
    '''
    # Define instrument overheads (in seconds)
    c       = [6.12243227e-04, 6.31621064e-01, 3.96040946e+01]
    read    = c[2] + c[1]*scanRatep + c[0]*scanRatep**2
    # Correlation between scanHeight/scanRate and pointing overhead was determined elsewhere
    if scanDirection == 'Round Trip':
        # Round Trip scan direction doesn't have to return to starting point, therefore no overhead
        pointing    = 0.
    elif scanDirection == 'Forward':
        c           = [  3.18485340e+01,   3.32968829e-02,   1.65687590e-02,   
                         7.65510038e-01,  -6.24504499e+01,   5.51452028e-03]
        pointing    = c[0]*(1 - np.exp(-c[2]*(scanHeight-c[4]))) + c[1]*scanHeight + c[3]*scanRatep +c[5]*scanRatep**2
    else:
        print("****HALTED: Unknown scan direction: %s" % scanDirection)
        return
    # Estimate total frame time including overheads
    tottime     = exptime+read+pointing         #seconds
    
    return exptime, tottime, scanRate, scanHeight, fluence

def wfc3_TExoNS(dictinput):
    '''
    Compute the transit depth uncertainty for a defined system and number of spectrophotometric channels.
    
    :param dictinput: dictionary containing instrument parameters and exoplanet specific parameters. {"pandeia_input":dict1, "pandexo_input":dict1}
    :type inputdict: dict
    :returns: 
        deptherr--transit depth uncertainty per spectrophotometric channel
        chanrms--light curve root mean squarerms
        ptsOrbit--number of HST orbits per visit
    :rtype: array of float,float,float
    
    HISTORY
    -------
    Written by Kevin Stevenson      October 2016
    '''
    pandeia_input = dictinput['pandeia_input']
    pandexo_input = dictinput['pandexo_input'] 
        
    #Assumptions: H-band
    hmag            = pandexo_input['star']['mag']
    trdur           = pandexo_input['planet']['transit_duration']
    numTr           = pandexo_input['observation']['noccultations']
    nchan           = pandexo_input['observation']['nchan']
    scanDirection   = pandexo_input['observation']['scanDirection']
    norbits         = pandexo_input['observation']['norbits']
    schedulability  = pandexo_input['observation']['schedulability']
    disperser       = pandeia_input['configuration']['instrument']['disperser'].lower()
    subarray        = pandeia_input['configuration']['detector']['subarray'].lower()
    nsamp           = pandeia_input['configuration']['detector']['nsamp']
    samp_seq        = pandeia_input['configuration']['detector']['samp_seq']    
    if isinstance(samp_seq, str):
        samp_seq    = samp_seq.lower()
    
    if disperser == 'g141':
        # Define reference Hmag, flux, variance, and exposure time for GJ1214
        refmag      = 9.094
        refflux     = 2.32e8
        refvar      = 2.99e8
        refexptime  = 88.436
    elif disperser == 'g102':
        # Define reference Hmag, flux, variance, and exposure time for WASP12
        refmag      = 10.228
        refflux     = 8.26e7
        refvar      = 9.75e7
        refexptime  = 103.129
    else:
        print("****HALTED: Unknown disperser: %s" % disperser)
        return
    
    # Determine max recommended scan height
    if subarray == 'grism512':
        maxScanHeight = 430
    elif subarray == 'grism256':
        maxScanHeight = 180
    else:
        print("****HALTED: Unknown subarray aperture: %s" % subarray)
        return
    
    # Define maximum frame time
    maxExptime  = 150.
    
    # Define available observing time per HST orbit in seconds
    if schedulability == '30':
        obsTime   = 51.3*60
    elif schedulability == '100':
        obsTime   = 46.3*60
    else:
        print("****HALTED: Unknown schedulability: %s" % schedulability)
        return
    
    # Compute recommended number of HST orbits and compare to user specified value
    guessorbits = wfc3_GuessNOrbits(trdur)
    if norbits == None:
        norbits = guessorbits
    elif norbits != guessorbits:
        print("****WARNING: Number of specified HST orbits does not match number of recommended orbits: %0.0f" % guessorbits)
    
    if nsamp == 0 or nsamp == None or samp_seq == None or samp_seq == "none":
        # Determine optimal nsamp and samp_seq values
        nsamp, samp_seq = wfc3_GuessParams(hmag, disperser, scanDirection, subarray, 
                                           obsTime, maxScanHeight, maxExptime)
    # Calculate observation parameters
    exptime, tottime, scanRate, scanHeight, fluence = wfc3_obs(hmag, disperser, scanDirection, 
                                                               subarray, nsamp, samp_seq)
    if scanHeight > maxScanHeight:
        print("****WARNING: Computed scan height exceeds maximum recommended height of %0.0f pixels." % maxScanHeight)
    if exptime > maxExptime:
        print("****WARNING: Computed frame time (%0.0f seconds) exceeds maximum recommended duration of %0.0f seconds." % (exptime,maxExptime))
    
    # Compute number of data points (frames) per orbit
    ptsOrbit    = np.floor(obsTime/tottime)
    # First point (frame) is always low, ignore when computing duty cycle
    dutyCycle   = (exptime*(ptsOrbit-1))/50./60*100
    
    # Compute number of non-destructive reads per orbit
    readsOrbit  = ptsOrbit*(nsamp+1)
    
    # Look for mid-orbit buffer dumps
    if (subarray == 'grism256') and (readsOrbit >= 300) and (exptime <= 43):
        print("****WARNING: Observing plan may incur mid-orbit buffer dumps.  Check with APT.")
    if (subarray == 'grism512') and (readsOrbit >= 120) and (exptime <= 100):
        print("****WARNING: Observing plan may incur mid-orbit buffer dumps.  Check with APT.")
    
    # Compute number of HST orbits per transit
    # ~96 minutes per HST orbit
    orbitsTr    = trdur/96./60.
    
    # Estimate number of good points during planet transit
    # First point in each HST orbit is flagged as bad; therefore, subtract from total
    if orbitsTr < 0.5:
        # Entire transit fits within one HST orbit
        ptsInTr  = ptsOrbit * orbitsTr/0.5 - 1
    elif orbitsTr <= 1.5:
        # Assume one orbit centered on mid-transit time
        ptsInTr = ptsOrbit - 1
    elif orbitsTr < 2.:
        # Assume one orbit during full transit and one orbit during ingress/egress
        ptsInTr = ptsOrbit * (np.floor(orbitsTr) + np.min((1,np.remainder(orbitsTr-np.floor(orbitsTr)-0.5,1)/0.5))) - 2
    else:
        # Assume transit contains 2+ orbits timed to maximize # of data points.
        ptsInTr  = ptsOrbit * (np.floor(orbitsTr) + np.min((1,np.remainder(orbitsTr-np.floor(orbitsTr),1)/0.5))) - np.ceil(orbitsTr)

    # Estimate number of good points outside of transit
    # Discard first HST orbit
    ptsOutTr    = (ptsOrbit-1) * (norbits-1) - ptsInTr
    
    # Compute transit depth uncertainty per spectrophotometric channel
    ratio       = 10**((refmag - hmag)/2.5)
    flux        = ratio*refflux*exptime/refexptime
    fluxvar     = ratio*refvar*exptime/refexptime
    chanflux    = flux/nchan
    chanvar     = fluxvar/nchan
    chanrms     = np.sqrt(chanvar)/chanflux*1e6     #ppm
    inTrrms     = chanrms/np.sqrt(ptsInTr*numTr)    #ppm
    outTrrms    = chanrms/np.sqrt(ptsOutTr*numTr)   #ppm
    deptherr    = np.sqrt(inTrrms**2 + outTrrms**2) #ppm
    
    info = {"Number of HST orbits": norbits,
            "WFC3 parameters: NSAMP": nsamp, 
            "WFC3 parameters: SAMP_SEQ":samp_seq.upper(),
            "Recommended scan rate (arcsec/s)": scanRate,
            "Scan height (pixels)": scanHeight,
            "Maximum pixel fluence (electrons)":fluence,
            "Estimated duty cycle (outside of Earth occultation)": dutyCycle,
            "Transit depth uncertainty(ppm)":deptherr,
            "Number of channels": nchan}
    
    return {"spec_error": deptherr/1e6, "light_curve_rms":chanrms/1e6, "nframes_per_orb":ptsOrbit,"info":info}

def calc_start_window(rms, ptsOrbit, numOrbits, depth, inc, aRs, period, tunc, duration=None, offset=0.):
    '''
    Plot earliest and latest possible spectroscopic light curves for given start window size
    Written by Kevin Stevenson      October 2016

    :param rms: light curve root-mean-square
    :param ptsOrbit: number of frames per HST orbit
    :param numOrbits:  number of HST orbits per visit
    :param depth: transit/eclipse depth
    :param inc: orbital inclination in degrees
    :param aRs: Semi-major axis in units of stellar radii (a/R*)
    :param period: orbital period in days
    :param tunc: float, +/- start time range in minutes
    :param duration: (Optional) full transit/eclipse duration in seconds
    :param offset: : (Optional) manual offset in observation start time, in minutes
    :type rms: float
    :type pltsOrbit: float
    :type numOrbits: float
    :type depth: float
    :type inc: float
    :type aRs: float
    :type period: float
    :type tunc: float
    :type duration: float
    :type offset: float
    :returns:
        minphase--earliest observation start phase
        maxphase--latest observation start phase
    :rtype: float,float
    '''
    import matplotlib.pyplot as plt
    import batman
    
    hstperiod   = 96./60/24                 # HST orbital period, days
    gsacq       = 0.                        # Guide star acquisition time, days
    punc        = tunc/60./24/period        # Start time range, phase
    cosi        = np.cos(inc*np.pi/180)     # Cosine of the inclination
    rprs        = np.sqrt(depth)            # Planet-star radius ratio
    if duration == None:                    # Transit duration
        duration    = period/np.pi*np.arcsin(1./aRs*np.sqrt(((1+rprs)**2-(aRs*cosi)**2)/(1-cosi**2)))

    params          = batman.TransitParams()
    params.t0       = 1.                    #time of inferior conjunction
    params.per      = 1.                    #orbital period is unity because units are phase
    params.rp       = rprs                  #planet radius (in units of stellar radii)
    params.a        = aRs                   #semi-major axis (in units of stellar radii)
    params.inc      = inc                   #orbital inclination (in degrees)
    params.ecc      = 0.                    #eccentricity
    params.w        = 90.                   #longitude of periastron (in degrees)
    params.u        = [0.0, 0.0]            #limb darkening coefficients
    params.limb_dark= "quadratic"           #limb darkening model

    phase1      = (period + duration/2. - hstperiod*(numOrbits-2) - hstperiod/2 + offset/24./60)/period
    phase2      = (period - duration/2. - hstperiod*2 + offset/24./60)/period
    minphase    = (phase1+phase2)/2-punc
    maxphase    = (phase1+phase2)/2+punc

    #Compute light curves at extremes of HST start window
    npts        = 4 * ptsOrbit * numOrbits
    phdur       = duration/period
    phase1      = np.linspace(minphase+hstperiod/period,minphase+hstperiod/period*(numOrbits-1)+hstperiod/period/2,npts)
    phase2      = np.linspace(maxphase+hstperiod/period,maxphase+hstperiod/period*(numOrbits-1)+hstperiod/period/2,npts)
    m           = batman.TransitModel(params, phase1)
    trmodel1    = m.light_curve(params)
    m           = batman.TransitModel(params, phase2)
    trmodel2    = m.light_curve(params)
    obsphase1   = []
    obsphase2   = []
    for i in range(numOrbits):
        obsphase1   = np.r_[obsphase1, np.linspace(minphase+hstperiod/period*i,minphase+hstperiod/period*i+hstperiod/period/2,ptsOrbit)]
        obsphase2   = np.r_[obsphase2, np.linspace(maxphase+hstperiod/period*i,maxphase+hstperiod/period*i+hstperiod/period/2,ptsOrbit)]
    m           = batman.TransitModel(params, obsphase1)
    obstr1      = m.light_curve(params) + np.random.normal(0, rms, obsphase1.shape)
    m           = batman.TransitModel(params, obsphase2)
    obstr2      = m.light_curve(params) + np.random.normal(0, rms, obsphase2.shape)
    
    return {'obsphase1':obsphase1,'light_curve_rms':rms, 'obstr1':obstr1,'obsphase2':obsphase2,
            'obstr2':obstr2,'minphase':minphase,'maxphase':maxphase,'phase1':phase1,
            'phase2':phase2,'trmodel1':trmodel1,'trmodel2':trmodel2}

def planet_spec(specfile, w_unit, disperser, deptherr, nchan, smooth=None):
    '''
    Plot exoplanet transmission/emission spectrum
    Written by Kevin Stevenson      October 2016

    :param specfile: filename for model spectrum [wavelength, flux]
    :param w_unit: wavelength unit (um or nm)
    :param disperser: grism (g102 or g141)
    :param deptherr: simulated transit/eclipse depth uncertainty
    :param nchan: number of spectrophotometric channels
    :param smooth: (Optional)length of smoothing kernel
    :type specfile: str
    :type w_unit: str
    :type disperser: str
    :type deptherr: float or array of length nchan
    :type nchan: float
    :type smooth: float
    :returns: plot
    '''
    import matplotlib.pyplot as plt
    # Load model wavelengths and spectrum
    mwave, mspec = np.loadtxt(specfile, unpack=True)
    # Convert wavelength to microns
    if w_unit == 'um':
        pass
    elif w_unit == 'nm':
        mwave /= 1000.
    else:
        print("****HALTED: Unrecognized wavelength unit: '%s'" % w_unit)
        return
    
    # Smooth model spectrum (optional)
    if smooth != None:
        import hst_smooth as sm
        mspec = sm.smooth(mspec, smooth)
    
    # Determine disperser wavelength boundaries
    if disperser == 'g141':
        wmin = 1.125
        wmax = 1.650
    elif disperser == 'g102':
        wmin = 0.84
        wmax = 1.13
    else:
        print("****HALTED: Unrecognized disperser name: '%s'" % disperser)
        return
    
    # Determine wavelength bins
    binsize     = (wmax - wmin)/nchan
    wave_low    = np.round([i for i in np.linspace(wmin, wmax-binsize, nchan)],3)
    wave_hi     = np.round([i for i in np.linspace(wmin+binsize, wmax, nchan)],3)
    binwave     = (wave_low + wave_hi)/2.
    
    # Create simulated spectrum by binning model spectrum and addding uncertainty
    binspec     = np.zeros(nchan)
    for i in range(nchan):
        ispec       = np.where((mwave >= wave_low[i])*(mwave <= wave_hi[i]))
        binspec[i]  = np.mean(mspec[ispec])
    binspec    += np.random.normal(0,deptherr,nchan)
    
    return {'model_wave':mwave,'model_spec':mspec,'binwave':binwave,'binspec':binspec,
             'error':deptherr,'wmin':wmin, 'wmax':wmax}
  
def compute_sim_hst(dictinput):
    """
    Function to set up explanet observations for HST only and 
    compute simulated spectrum.
    :param dictinput: instrument and pandexo dictionaries in format {"pandeia_input":dict1, "pandexo_input":dict2}
    :param type: dictionary
    :returns: dictionary with all hst output info needed to plot simulated data, light curves timing info
    :rtype: dictionary
    """
    pandexo_input   = dictinput['pandexo_input']
    pandeia_input   = dictinput['pandeia_input']
    
    disperser       = pandeia_input['configuration']['instrument']['disperser'].lower()
    hmag            = pandexo_input['star']['mag']
    nchan           = pandexo_input['observation']['nchan']
    specfile        = pandexo_input['planet']['exopath']
    w_unit          = pandexo_input['planet']['w_unit']
    numorbits       = pandexo_input['observation']['norbits']
    depth           = pandexo_input['planet']['depth']
    inc             = pandexo_input['planet']['i']
    aRs             = pandexo_input['planet']['ars']
    period          = pandexo_input['planet']['period']
    tunc            = 10 
    
    a = wfc3_TExoNS(dictinput)
    b = calc_start_window(a['light_curve_rms'], a['nframes_per_orb'], numorbits, depth, inc, aRs, period, tunc)
    c = planet_spec(specfile, w_unit, disperser, a['spec_error'], nchan,smooth=20) 
    
    info_div = create_out_div(a['info'], b['minphase'],b['maxphase'])
    
    return {"wfc3_TExoNS":a,"calc_start_window": b,"planet_spec":c,"info_div":info_div}
    
    
def create_out_div(input_dict,minphase,maxphase):
    """
    Function to render input dicts in html format for web front end
    
    :param input_dict: any input dictionary
    :param type: dictionary
    :returns: input_div html table
    :rtype: html div 
    """
    input_dict['Start observations between orbital phases'] = str(minphase)+'-'+str(maxphase)
    input_div = pd.DataFrame(input_dict.items(), columns=['Component', 'Values']).to_html().encode()
    input_div = '<table class="table table-striped"> \n' + input_div[36:len(input_div)]
    return input_div
    
